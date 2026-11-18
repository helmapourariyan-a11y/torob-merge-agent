"""Review operator-supplied product evidence and emit a JSON recommendation."""

import argparse
import json
import re
import sys
import unicodedata

CONDITION = re.compile(r"(?<!\w)(استوک|کارکرده|جعبه[-\s‌]*باز)(?!\w)")
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩يك", "01234567890123456789یک")


def normalize(value):
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value).translate(DIGITS).casefold()
    return " ".join(value.split())


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
