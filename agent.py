"""Review operator-supplied product evidence and emit a JSON recommendation."""

import argparse
import json
import re
import sys
import unicodedata

CONDITION = re.compile(r"(?<!\w)(استوک|کارکرده|جعبه[-\s‌]*باز)(?!\w)")
CASE_MODEL_PAIR = re.compile(r'(?<![\w/])(1[0-9]|20)\s*/\s*(1[0-9]|20)(?![\w/])')
IPHONE_MODEL = re.compile(
    r"(?<!\w)(?:iphone|آیفون|ایفون|آی فون|ای فون)\s*-?\s*"
    r"(1[0-9]|20|[6-9]|xr|xs|x|se)(?!\w)"
    r"(?:\s+(pro\s*max|پرو\s*مکس|pro|پرو|plus|پلاس|mini|مینی|max|مکس))?(?!\w)"
)
IPHONE_VARIANTS = {
    "promax": "pro max", "پرو مکس": "pro max", "پرو‌مکس": "pro max",
    "پرومکس": "pro max", "پرو": "pro", "پلاس": "plus", "مینی": "mini", "مکس": "max",
}

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩يك", "01234567890123456789یک")


def normalize(value):
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value).translate(DIGITS).casefold()
    return " ".join(value.split())


def distinct_iphone_model(title):
    title = normalize(title).replace("‌", " ")
    # Slash and range notation can introduce another model without repeating the brand.
    if "/" in title or re.search(r"\d\s*(?:و|یا|تا|[-–])\s*\d", title):
        return ""
    models = set()
    for family, variant in IPHONE_MODEL.findall(title):
        models.add((family, IPHONE_VARIANTS.get(variant, variant)))
    if len(models) != 1:
        return ""
    family, variant = models.pop()
    if family == "se":
        return ""  # An SE title alone can omit the generation.
    return f"{family} {variant}".strip()


def decision(action, reason, **details):
    return {"decision": action, "reason": reason, **details}


def review(request):
    kind = request.get("kind")
    if kind == "split":
        return review_split(request)
    if kind != "merge":
        return decision("review", "برای این نوع درخواست قواعد کافی ثبت نشده است.")
    left, right = request.get("left"), request.get("right")
    if not isinstance(left, dict) or not isinstance(right, dict):
        return decision("review", "شواهد هر دو محصول لازم است.")

    if request.get("conflicting_evidence") is True:
        return decision("review", "عنوان‌ها، تصاویر یا کدهای ثبت‌شده با هم تعارض دارند.")

    if request.get("category") == "phone_case":
        for product in (left, right):
            title = normalize(product.get("title"))
            pair = CASE_MODEL_PAIR.search(title)
            if "قاب" in title and pair and pair[1] != pair[2]:
                return decision(
                    "reject", "عنوان قاب دو مدل گوشی را معرفی می‌کند.",
                    reason_code="multiple_phone_models_in_title",
                )

        first_model = distinct_iphone_model(left.get("title"))
        second_model = distinct_iphone_model(right.get("title"))
        if first_model and second_model and first_model != second_model:
            return decision(
                "reject", f"مدل گوشی در عنوان‌ها متفاوت است (iPhone {first_model} / iPhone {second_model}).",
                reason_code="different_phone_models",
            )

    for field, reason in {
        "brand": "برند تجاری محصولات متفاوت است.",
        "model": "مدل تجاری محصولات متفاوت است.",
        "structure": "ساختار محصولات متفاوت است.",
        "quantity": "تعداد کالا در بسته متفاوت است.",
        "condition": "وضعیت کالاها متفاوت است.",
    }.items():
        first, second = (normalize(item.get(field)) for item in (left, right))
        if first and second and first != second:
            return decision("reject", reason)

    if request.get("category") == "cable":
        lengths = [normalize(item.get("length")) for item in (left, right)]
        if all(lengths) and lengths[0] != lengths[1]:
            return decision("reject", "طول کابل‌ها متفاوت است.")
        if any(lengths) and not all(lengths):
            if request.get("images_checked") is True:
                return decision("reject", "طول یکی از کابل‌ها پس از بررسی تصاویر نامشخص است.")
            return decision("review", "برای طول کابل، عکس‌های بسته‌بندی را بررسی کنید.")
        if not any(lengths):
            return decision("review", "طول هر دو کابل باید مشخص شود.")

    if any(CONDITION.search(normalize(item.get("title"))) for item in (left, right)):
        if not all(normalize(item.get("condition")) for item in (left, right)):
            return decision("review", "وضعیت هر دو کالا را بررسی کنید.")

    required = {
        "phone_case": ("phone_model", "camera_cover", "magsafe"),
        "headphones": ("connection", "anc"),
        "cable": ("connectors",),
        "smartwatch": ("commercial_size", "bundle"),
    }
    category = request.get("category")
    if not isinstance(category, str) or category not in required:
        return decision("review", "دستهٔ محصول به بررسی انسانی نیاز دارد.")
    fields = ("title", "brand", "model", "structure", "condition", "quantity")
    comparisons = [(normalize(left.get(field)), normalize(right.get(field))) for field in required[category]]
    if any(first and second and first != second for first, second in comparisons):
        return decision("reject", "ویژگی تعیین‌کنندهٔ دسته متفاوت است.")
    if category == "smartwatch":
        sim = {normalize(item.get("sim_support")) for item in (left, right)}
        if sim == {"yes", "no"}:
            return decision("reject", "پشتیبانی سیم‌کارت متفاوت است.")
    if (
        request.get("images_checked") is True
        and request.get("cluster_checked") is True
        and request.get("single_model_confirmed") is True
        and all(normalize(item.get(field)) for item in (left, right) for field in fields)
        and all(first and second for first, second in comparisons)
    ):
        return decision("approve", "")
    return decision("review", "شواهد لازم برای تأیید کامل نیست.")


def review_split(request):
    groups = request.get("verified_split_groups")
    if request.get("cluster_checked") is not True or not isinstance(groups, list) or not groups:
        return decision("review", "فهرست کامل کلاستر و گروه‌های جداسازی باید بررسی شوند.")
    members = set()
    for group in groups:
        if not isinstance(group, list) or not group:
            return decision("review", "هر گروه جداسازی باید دست‌کم یک عضو داشته باشد.")
        for member in group:
            if not isinstance(member, str) or not member.strip() or member in members:
                return decision("review", "شناسهٔ اعضا باید معتبر و بدون تکرار باشد.")
            members.add(member)
    return decision("split", "گروه‌های پیشنهادی برای تأیید کارشناس آماده‌اند.", groups=groups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("expected a JSON object")
    except ValueError as error:
        parser.exit(2, f"Invalid request: {error}\n")
    print(json.dumps(review(request), ensure_ascii=False))


if __name__ == "__main__":
    main()
