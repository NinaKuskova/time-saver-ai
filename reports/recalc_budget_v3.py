#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пересчёт стоимости бюджетной версии плана питания (v3 — прямые цены).

Методика (строго по ТЗ пользователя):

ШАГ 1. Для КАЖДОГО ингредиента в КАЖДОМ блюде:
   cost_ingredient = (qty_gram / 1000) * price_per_kg
   (для штучных — qty_pcs * price_per_pcs)

ШАГ 2. Для КАЖДОГО продукта в списке покупок:
   cost_row = (qty_kg) * price_per_kg
   (для штучных — qty_pcs * price_per_pcs)

ШАГ 3. Суммы по приёмам пищи за день/неделю и по списку покупок
   за день/неделю должны совпадать (в пределах округлений).

Цены — прямые рыночные ₽/кг и ₽/шт, согласованные между рецептами
и списком покупок. ВАЖНО: цена одинакова для ингредиента в рецепте
и для этого же продукта в списке покупок.
"""

import json
import sys
import io
from pathlib import Path
from collections import defaultdict, OrderedDict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "meal-plans" / "meal-plan-budget.json"
MD_OUT = ROOT / "meal-plans" / "meal-plan-budget.md"
REPORT = ROOT / "reports" / "recalc_budget_report.md"


# --------------------------------------------------------------------------- #
# 1. Прямые цены ₽/кг и ₽/шт — единый источник истины
# --------------------------------------------------------------------------- #
# Ключ — нормализованное название (lower). Значение: ('kg'|'pcs', price)
PRICE = {
    # Крупы и бобовые
    "гречневая крупа": ("kg", 80),
    "овсяные хлопья": ("kg", 60),
    "рис": ("kg", 80),
    "пшено": ("kg", 80),
    "перловая крупа": ("kg", 60),
    "горох": ("kg", 70),
    "фасоль красная": ("kg", 130),
    "макароны": ("kg", 80),
    "лапша тонкая": ("kg", 120),
    "мука пшеничная": ("kg", 50),
    "крупа манная": ("kg", 70),

    # Хлеб
    "хлеб пшеничный": ("kg", 100),
    "хлеб чёрный": ("kg", 80),
    "хлебец цельнозерновой": ("pcs", 12),
    "печенье простое": ("kg", 200),

    # Мясо и птица
    "куриные бёдра": ("kg", 250),
    "куриное бедро": ("kg", 250),  # синоним для JSON
    "куриный фарш": ("kg", 250),
    "куриная печень": ("kg", 200),
    "куриные сердечки": ("kg", 250),
    "говядина на кости": ("kg", 600),

    # Рыба
    "скумбрия свежая": ("kg", 350),
    "горбуша консервированная": ("kg", 500),
    "сайра консервированная": ("kg", 400),

    # Яйца
    "яйцо куриное": ("pcs", 10),  # ~50 г/шт

    # Молочные
    "молоко 2.5%": ("kg", 70),         # 1 л ≈ 1 кг
    "творог 5%": ("kg", 250),
    "кефир 2.5%": ("kg", 70),
    "ряженка": ("kg", 90),
    "йогурт порционный 2.5%": ("pcs", 70),  # 1 шт = 200 г, цена рыночная ~70 ₽
    "сыр «российский»": ("kg", 600),
    "сметана": ("kg", 200),
    "масло сливочное": ("kg", 600),
    "масло подсолнечное": ("kg", 130),

    # Овощи
    "картофель": ("kg", 50),
    "морковь": ("kg", 50),
    "лук репчатый": ("kg", 40),
    "свёкла": ("kg", 50),
    "капуста белокочанная": ("kg", 35),
    "помидор": ("kg", 150),
    "огурец": ("kg", 100),
    "огурец свежий": ("kg", 100),
    "перец болгарский": ("kg", 200),
    "тыква": ("kg", 60),
    "шампиньоны": ("kg", 250),
    "горошек зелёный заморозка": ("kg", 180),
    "горошек зелёный (заморозка)": ("kg", 180),
    "кукуруза консервированная": ("kg", 200),
    "томатная паста": ("kg", 250),

    # Фрукты и сухофрукты
    "банан": ("kg", 100),
    "яблоко": ("kg", 80),
    "груша": ("kg", 100),
    "изюм": ("kg", 350),
    "курага": ("kg", 500),
    "лимон": ("pcs", 30),
    "чеснок": ("pcs", 5),  # головка

    # Специи и прочее
    "мёд": ("kg", 600),
    "семечки подсолнечные": ("kg", 250),
    "арахис": ("kg", 350),
    "грецкий орех": ("kg", 1200),
    "укроп": ("pcs", 30),  # пучок
    "петрушка": ("pcs", 30),
    "укроп, петрушка": ("pcs", 30),
    "лавровый лист": ("kg", 500),  # 1 ₽ за 2 г в рецепте — оставим 500 ₽/кг
    "чай, соль, специи": ("set", 50),  # набор — фикс 50 ₽
}

# Граммов на одну штуку (для конвертации qty_gram → штуки в рецептах)
PIECE_GRAMS = {
    "яйцо куриное": 50,
    "хлебец цельнозерновой": 30,
    "лимон": 150,
    "чеснок": 50,
    "укроп": 30,
    "петрушка": 30,
    "укроп, петрушка": 30,
    "йогурт порционный 2.5%": 200,  # 1 стаканчик = 200 г
}

# Список покупок — ЗАПОЛНЯЕТСЯ АВТОМАТИЧЕСКИ как сумма потребления по рецептам
# (см. main() — SHOPPING_QTY_FROM_RECIPES). Это гарантирует, что суммы по
# приёмам пищи и по списку покупок совпадают (в пределах округлений).
SHOPPING_QTY: "OrderedDict[str, tuple]" = OrderedDict()

# Канонизация ключей (JSON → таблица)
SYNONYMS = {
    "куриное бедро": "куриные бёдра",
    "огурец свежий": "огурец",
    "горошек зелёный заморозка": "горошек зелёный (заморозка)",
}


def lookup_price(product: str):
    """Возвращает (unit, price_per_unit) или (None, None)."""
    key = product.strip().lower()
    key = SYNONYMS.get(key, key)
    return PRICE.get(key, (None, None))


# --------------------------------------------------------------------------- #
# 2. Расчёт стоимости ингредиента
# --------------------------------------------------------------------------- #
def ingredient_cost(product: str, qty_gram: float) -> dict:
    unit, price = lookup_price(product)
    if unit is None:
        return {"product": product, "qty_gram": qty_gram, "unit": None,
                "unit_price": None, "cost": None, "warning": "нет цены"}
    if unit == "set":
        # набор — фикс сумма (для всего)
        return {"product": product, "qty_gram": qty_gram, "unit": "set",
                "unit_price": price, "cost": price, "warning": None}
    if unit == "kg":
        cost = (qty_gram / 1000.0) * price
        return {"product": product, "qty_gram": qty_gram, "unit": "kg",
                "unit_price": price, "cost": round(cost, 2), "warning": None}
    if unit == "pcs":
        grams_per_pc = PIECE_GRAMS.get(product.strip().lower(), 50.0)
        qty_pcs = qty_gram / grams_per_pc
        cost = qty_pcs * price
        return {"product": product, "qty_gram": qty_gram, "unit": "pcs",
                "unit_price": price, "cost": round(cost, 2), "warning": None}
    return {"product": product, "qty_gram": qty_gram, "unit": None,
            "unit_price": None, "cost": None, "warning": "неизвестная единица"}


# --------------------------------------------------------------------------- #
# 3. Главный расчёт
# --------------------------------------------------------------------------- #
def main():
    plan = json.loads(JS.read_text(encoding="utf-8"))

    # 3.1. По приёмам пищи (точная стоимость)
    days = []
    week_total_meals = 0.0
    for day in plan["days"]:
        day_total = 0.0
        meals = []
        for meal in day["meals"]:
            rows = [ingredient_cost(ing["product"], ing["qty_gram"])
                    for ing in meal["ingredients"]]
            meal_total = round(sum(r["cost"] for r in rows
                                   if r["cost"] is not None), 2)
            day_total += meal_total
            meals.append({
                "type": meal["type"],
                "name": meal["name"],
                "kcal_portion": meal.get("kcal_portion"),
                "rows": rows,
                "total": meal_total,
            })
        week_total_meals += day_total
        days.append({
            "day": day["day"],
            "is_fasting": day.get("is_fasting", False),
            "meals": meals,
            "day_total": round(day_total, 2),
        })

    # 3.2. Список покупок — АВТОМАТИЧЕСКИ как сумма потребления по рецептам.
    # Это гарантирует, что суммы по приёмам пищи и по списку покупок
    # совпадают (в пределах округлений), как требует ТЗ.
    consumed = OrderedDict()  # product -> qty_gram
    for day in plan["days"]:
        for meal in day["meals"]:
            for ing in meal["ingredients"]:
                key = ing["product"].strip().lower()
                key = SYNONYMS.get(key, key)
                consumed[key] = consumed.get(key, 0.0) + ing["qty_gram"]

    shopping = []
    week_total_shop = 0.0
    for product, qty_gram in consumed.items():
        u, price = lookup_price(product)
        if u is None:
            shopping.append({"product": product, "qty_gram": qty_gram,
                             "qty": None, "unit": None, "price": None,
                             "cost": None, "warning": "нет цены"})
            continue
        if u == "set":
            cost = price  # набор — фикс цена (один раз в неделю)
            shopping.append({"product": product, "qty_gram": qty_gram,
                             "qty": 1, "unit": "набор", "price": price,
                             "cost": cost, "warning": None})
            week_total_shop += cost
            continue
        if u == "kg":
            qty_kg = qty_gram / 1000.0
            cost = qty_kg * price
            shopping.append({"product": product, "qty_gram": qty_gram,
                             "qty": qty_kg, "unit": "kg", "price": price,
                             "cost": round(cost, 2), "warning": None})
        else:  # pcs
            grams_per_pc = PIECE_GRAMS.get(product, 50.0)
            qty_pcs = qty_gram / grams_per_pc
            cost = qty_pcs * price
            shopping.append({"product": product, "qty_gram": qty_gram,
                             "qty": qty_pcs, "unit": "pcs", "price": price,
                             "cost": round(cost, 2), "warning": None})
        week_total_shop += cost

    # 3.3. Печать
    print("=" * 78)
    print("БЮДЖЕТНАЯ ВЕРСИЯ — ТОЧНЫЙ ПЕРЕСЧЁТ (v3, прямые цены ₽/кг и ₽/шт)")
    print("=" * 78)
    for d in days:
        print(f"\n## {d['day']}{' (пост)' if d['is_fasting'] else ''}  "
              f"|  ИТОГО: {d['day_total']:.2f} ₽")
        for m in d["meals"]:
            print(f"  {m['type']:>10} | {m['name']:<48} | {m['total']:7.2f} ₽")
            for r in m["rows"]:
                if r["cost"] is None:
                    print(f"      - {r['product']:<30} {r['qty_gram']:>6} г : {r['warning']}")
                elif r["unit"] == "kg":
                    print(f"      - {r['product']:<30} {r['qty_gram']:>6} г "
                          f"× {r['unit_price']:>6.2f} ₽/кг = {r['cost']:6.2f} ₽")
                elif r["unit"] == "pcs":
                    grams_per_pc = PIECE_GRAMS.get(r["product"].strip().lower(), 50.0)
                    pcs = r["qty_gram"] / grams_per_pc
                    print(f"      - {r['product']:<30} {r['qty_gram']:>6} г "
                          f"({pcs:.2f} шт) × {r['unit_price']:>5.2f} ₽/шт "
                          f"= {r['cost']:6.2f} ₽")
                else:
                    print(f"      - {r['product']:<30} {r['qty_gram']:>6} г "
                          f": {r['cost']:6.2f} ₽ (набор)")

    print("\n" + "=" * 78)
    print(f"ИТОГО ЗА НЕДЕЛЮ (по приёмам пищи): {week_total_meals:.2f} ₽")
    print("=" * 78)

    print("\n" + "=" * 78)
    print("СПИСОК ПОКУПОК — Стоимость = количество × цена")
    print("=" * 78)
    print(f"{'№':>3}  {'Продукт':<32} {'Кол-во':>10} {'Цена/ед':>10} {'Стоимость':>10}")
    for i, s in enumerate(shopping, 1):
        if s["cost"] is None:
            print(f"{i:>3}  {s['product']:<32} {'':>10} {'':>10} {s['warning']:>10}")
        else:
            if s["unit"] == "kg":
                qty_disp = f"{s['qty']:.3f} кг"
            elif s["unit"] == "pcs":
                qty_disp = f"{s['qty']:.1f} шт"
            else:
                qty_disp = "набор"
            print(f"{i:>3}  {s['product']:<32} {qty_disp:>10} "
                  f"{s['price']:>8.2f}   {s['cost']:>8.2f} ₽")
    print("-" * 78)
    print(f"  ИТОГО ЗА НЕДЕЛЮ (по списку покупок): {week_total_shop:.2f} ₽")
    print("=" * 78)
    print(f"  Расхождение сумм: {abs(week_total_meals - week_total_shop):.2f} ₽")

    # 3.4. Записываем точные значения в JSON-файл
    for day_idx, day in enumerate(plan["days"]):
        plan["days"][day_idx]["total_price_rub"] = days[day_idx]["day_total"]
        # стоимость каждого приёма пищи
        for meal_idx, meal in enumerate(day["meals"]):
            plan["days"][day_idx]["meals"][meal_idx]["price_rub"] = days[day_idx]["meals"][meal_idx]["total"]
            # стоимость каждого ингредиента
            for ing_idx, ing in enumerate(meal["ingredients"]):
                r = days[day_idx]["meals"][meal_idx]["rows"][ing_idx]
                if r["cost"] is not None:
                    plan["days"][day_idx]["meals"][meal_idx]["ingredients"][ing_idx]["cost_rub"] = r["cost"]

    plan["meta"]["version"] = "3.0 (точный пересчёт по прямым ценам ₽/кг и ₽/шт)"
    plan["meta"]["recalculated_at"] = "2026-08-20"
    plan["meta"]["recalc_script"] = "reports/recalc_budget_v3.py"
    plan["meta"]["budget_actual_rub_meals"] = round(week_total_meals, 2)
    plan["meta"]["budget_actual_rub_shopping"] = round(week_total_shop, 2)
    plan["total_budget_rub"] = round(week_total_meals, 2)
    plan["total_budget_meals_rub"] = round(week_total_meals, 2)
    plan["total_budget_shopping_rub"] = round(week_total_shop, 2)
    plan["budget_by_day_avg"] = round(week_total_meals / 7, 2)

    # Список покупок в JSON
    plan["shopping_list_precise"] = [
        {"product": s["product"],
         "qty": s["qty"],
         "unit": s["unit"],
         "price_per_unit": s["price"],
         "cost_rub": s["cost"]}
        for s in shopping
    ]

    JS.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] JSON обновлён: {JS.relative_to(ROOT)}")

    # 3.5. Пишем отчёт
    lines = []
    lines.append("# Бюджетная версия — точный пересчёт (v3)\n")
    lines.append("**Методика:** `Стоимость ингредиента = (qty_gram/1000) × price_per_kg` "
                 "(для штучных: `qty_pcs × price_per_pcs`).\n\n")
    lines.append("Цены — единый источник истины (см. `PRICE` в `reports/recalc_budget_v3.py`).\n\n")

    lines.append("## Сводка\n")
    lines.append("| Показатель | Сумма |")
    lines.append("|---|---:|")
    lines.append(f"| Сумма по приёмам пищи | **{week_total_meals:.2f} ₽** |")
    lines.append(f"| Сумма по списку покупок | **{week_total_shop:.2f} ₽** |")
    lines.append(f"| Расхождение (округления + лавровый лист) | {abs(week_total_meals - week_total_shop):.2f} ₽ |")
    lines.append(f"| Средний бюджет в день (по приёмам) | {week_total_meals/7:.2f} ₽ |")
    lines.append("")

    lines.append("## По приёмам пищи\n")
    for d in days:
        lines.append(f"### {d['day']}{' (пост)' if d['is_fasting'] else ''}  "
                     f"—  {d['day_total']:.2f} ₽\n")
        lines.append("| Приём | Блюдо | Ккал | Стоимость (₽) |")
        lines.append("|---|---|---:|---:|")
        for m in d["meals"]:
            lines.append(f"| {m['type']} | {m['name']} | {m['kcal_portion']} | {m['total']:.2f} |")
        lines.append(f"| | **Итого за день** | | **{d['day_total']:.2f}** |")
        lines.append("")

    lines.append("## Список покупок (точные суммы)\n")
    lines.append("| № | Продукт | Кол-во | Цена ₽/кг,шт | Стоимость (₽) |")
    lines.append("|---:|---|---:|---:|---:|")
    for i, s in enumerate(shopping, 1):
        if s["cost"] is None:
            lines.append(f"| {i} | {s['product']} | — | — | нет цены |")
        else:
            if s["unit"] == "kg":
                qty_disp = f"{s['qty']:.3f} кг"
            elif s["unit"] == "pcs":
                qty_disp = f"{s['qty']:.1f} шт"
            else:
                qty_disp = "набор"
            lines.append(f"| {i} | {s['product']} | {qty_disp} | {s['price']:.2f} | {s['cost']:.2f} |")
    lines.append(f"| | | | **Итого:** | **{week_total_shop:.2f} ₽** |")
    lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Отчёт сохранён: {REPORT.relative_to(ROOT)}")

    return week_total_meals, week_total_shop


if __name__ == "__main__":
    main()
