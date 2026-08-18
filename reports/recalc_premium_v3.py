#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пересчёт стоимости Premium-версии плана питания (v3 — прямые цены).

Методика (строго по ТЗ пользователя):

ШАГ 1. Для КАЖДОГО ингредиента в КАЖДОМ блюде:
   cost_ingredient = (qty_gram / 1000) * price_per_kg
   (для штучных — qty_pcs * price_per_pcs)

ШАГ 2. Для КАЖДОГО продукта в списке покупок:
   cost_row = (qty_kg) * price_per_kg
   (для штучных — qty_pcs * price_per_pcs)

ШАГ 3. Суммы по приёмам пищи и по списку покупок должны совпадать.

Цены — прямые рыночные ₽/кг и ₽/шт, единый источник истины.
"""

import json
import sys
import io
from pathlib import Path
from collections import OrderedDict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "meal-plans" / "meal-plan-premium.json"
MD_OUT = ROOT / "meal-plans" / "meal-plan-premium.md"
REPORT = ROOT / "reports" / "2026-08-15_premium-recalc-v3.md"


# --------------------------------------------------------------------------- #
# 1. Прямые цены ₽/кг и ₽/шт — единый источник истины
# --------------------------------------------------------------------------- #
# Ключ — нормализованное название (lower). Значение: ('kg'|'pcs'|'ml', price)
PRICE = {
    # Крупы и паста
    "овсяные хлопья": ("kg", 60),
    "киноа": ("kg", 540),
    "булгур": ("kg", 320),
    "рис басмати": ("kg", 250),
    "паста (пенне)": ("kg", 330),
    "тальятелле": ("kg", 560),
    "мука пшеничная": ("kg", 50),

    # Хлеб и хлебцы
    "хлеб цельнозерновой": ("kg", 220),
    "хлеб чиабатта": ("kg", 420),
    "хлебцы цельнозерновые": ("pcs", 35),  # ~10 г/шт (см. PIECE_GRAMS)
    "гранола": ("kg", 1000),

    # Мясо и птица
    "говядина (стейк)": ("kg", 1300),
    "говядина (мякоть)": ("kg", 1100),
    "говяжья печень": ("kg", 700),
    "куриная грудка (охлаждённая)": ("kg", 550),
    "утиная грудка": ("kg", 1300),

    # Рыба и морепродукты
    "сёмга слабосолёная": ("kg", 1950),
    "форель (филе)": ("kg", 1180),
    "треска (филе)": ("kg", 875),
    "тунец (стейк)": ("kg", 1700),

    # Молочные
    "зернёный творог 5%": ("kg", 470),  # 60 г
    "рикотта": ("kg", 560),
    "маскарпоне": ("kg", 920),
    "греческий йогурт 2%": ("kg", 350),
    "фета": ("kg", 1380),
    "пармезан": ("kg", 3000),
    "сливки 20%": ("kg", 360),
    "молоко 3.2%": ("kg", 80),
    "масло сливочное 82.5%": ("kg", 900),

    # Яйца
    "яйцо куриное": ("pcs", 10),

    # Масла и соусы
    "масло оливковое extra virgin": ("ml", 3),  # 500 мл ≈ 1500 ₽
    "хумус готовый": ("kg", 440),

    # Бобовые
    "фасоль белая (консерв.)": ("kg", 350),
    "чечевица красная": ("kg", 310),

    # Овощи и зелень
    "авокадо": ("pcs", 90),  # 1 шт ~240 г
    "томаты в собственном соку": ("kg", 175),
    "томатный соус (passata)": ("kg", 220),
    "оливки": ("kg", 900),
    "каперсы": ("kg", 1200),
    "белые грибы (заморозка)": ("kg", 640),
    "брокколи": ("kg", 300),
    "тыква": ("kg", 80),
    "картофель (молодой)": ("kg", 130),
    "морковь": ("kg", 50),
    "лук репчатый": ("kg", 40),
    "лук красный": ("kg", 270),
    "чеснок": ("pcs", 30),  # головка
    "перец болгарский": ("kg", 250),
    "помидоры черри": ("kg", 320),
    "капуста белокочанная": ("kg", 40),
    "цуккини": ("kg", 250),
    "баклажан": ("kg", 180),
    "шпинат": ("kg", 700),
    "микс салат": ("kg", 600),
    "руккола": ("kg", 1400),
    "микрозелень": ("kg", 1800),
    "зелень (руккола)": ("kg", 1400),
    "руккола": ("kg", 1400),
    "укроп": ("pcs", 30),
    "петрушка": ("pcs", 30),
    "укроп, петрушка": ("pcs", 30),
    "эдамаме (бобы)": ("kg", 750),

    # Фрукты и ягоды
    "манго": ("kg", 650),
    "груша": ("kg", 220),
    "персик": ("kg", 440),
    "яблоко": ("kg", 95),
    "голубика свежая": ("kg", 1000),
    "малина свежая": ("kg", 1100),
    "банан": ("kg", 115),
    "гранат (зёрна)": ("kg", 1000),
    "гранат": ("pcs", 80),
    "вишня (заморозка)": ("kg", 440),

    # Орехи и сухофрукты
    "курага": ("kg", 830),
    "чернослив": ("kg", 720),
    "финики": ("kg", 580),
    "миндаль жареный": ("kg", 1750),
    "миндаль": ("kg", 1800),
    "грецкие орехи": ("kg", 1600),
    "тыквенные семечки": ("kg", 1500),

    # Специи и подсластители
    "мёд": ("kg", 900),
    "кленовый сироп": ("ml", 1.5),  # 250 мл ≈ 600 ₽
    "лимон": ("pcs", 25),
    "бальзамический уксус": ("ml", 2.4),  # 250 мл ≈ 600 ₽
    "красное вино (для соуса)": ("ml", 0.6),  # 750 мл ≈ 450 ₽
    "карри (смесь специй)": ("kg", 1500),
    "специи (тимьян, паприка, корица, соль, перец)": ("set", 87),
    "тимьян, паприка, корица, соль, перец": ("set", 80),
    "хумус": ("kg", 440),
    "хумус готовый": ("kg", 440),
    "специи": ("set", 50),
}

# Граммов на одну штуку / мл на одну штуку
PIECE_GRAMS = {
    "яйцо куриное": 50,
    "хлебцы цельнозерновые": 25,        # 1 хлебец ~25 г (4 шт = 100 г, 60 г = ~2.4 шт)
    "лимон": 150,
    "чеснок": 50,
    "укроп": 30,
    "петрушка": 30,
    "укроп, петрушка": 30,
    "авокадо": 240,                      # ~240 г/шт
    "гранат": 350,                        # ~350 г/шт
}

# Специальные случаи: цена за мл (для жидкостей)
PIECE_ML = {
    "масло оливковое extra virgin": 1000,  # 500 мл ≈ 1500 ₽ → 3 ₽/мл; qty_gram ≈ qty_ml (плотность 0.92)
    "кленовый сироп": 1000,                 # 1000 мл ≈ 1500 ₽
    "бальзамический уксус": 500,            # 500 мл ≈ 600 ₽
    "красное вино (для соуса)": 750,        # 750 мл ≈ 450 ₽
}

# Канонизация названий
SYNONYMS = {
    "хлебцы цельнозерновые": "хлебцы цельнозерновые",
    "миндаль жареный": "миндаль",
    "гранат (зёрна)": "гранат",
    "зелень (руккола)": "руккола",
    "хумус готовый": "хумус",
}


def normalize(name: str) -> str:
    """Канонизация имени для consumption-словаря."""
    n = name.strip().lower()
    return SYNONYMS.get(n, n)


def lookup_price(product: str):
    """Возвращает (unit, price_per_unit)."""
    key = normalize(product)
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
        return {"product": product, "qty_gram": qty_gram, "unit": "set",
                "unit_price": price, "cost": price, "warning": None}
    if unit == "ml":
        # жидкости — qty_gram ≈ qty_ml (плотность ~1)
        cost = qty_gram * price
        return {"product": product, "qty_gram": qty_gram, "unit": "ml",
                "unit_price": price, "cost": round(cost, 2), "warning": None}
    if unit == "kg":
        cost = (qty_gram / 1000.0) * price
        return {"product": product, "qty_gram": qty_gram, "unit": "kg",
                "unit_price": price, "cost": round(cost, 2), "warning": None}
    if unit == "pcs":
        # Ищем по канонизированному имени (Гранат (зёрна) → гранат → 350 г/шт)
        key = normalize(product)
        grams_per_pc = PIECE_GRAMS.get(key, 50.0)
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

    # Список покупок — АВТОМАТИЧЕСКИ как сумма потребления
    consumed = OrderedDict()
    for day in plan["days"]:
        for meal in day["meals"]:
            for ing in meal["ingredients"]:
                key = normalize(ing["product"])
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
            shopping.append({"product": product, "qty_gram": qty_gram,
                             "qty": 1, "unit": "набор", "price": price,
                             "cost": price, "warning": None})
            week_total_shop += price
            continue
        if u == "ml":
            qty_ml = qty_gram
            cost = qty_ml * price
            shopping.append({"product": product, "qty_gram": qty_gram,
                             "qty": qty_ml, "unit": "ml", "price": price,
                             "cost": round(cost, 2), "warning": None})
        elif u == "kg":
            qty_kg = qty_gram / 1000.0
            cost = qty_kg * price
            shopping.append({"product": product, "qty_gram": qty_gram,
                             "qty": qty_kg, "unit": "kg", "price": price,
                             "cost": round(cost, 2), "warning": None})
        else:  # pcs
            # Ищем по канонизированному имени (Гранат (зёрна) → гранат → 350 г/шт)
            grams_per_pc = PIECE_GRAMS.get(product, PIECE_GRAMS.get(normalize(product), 50.0))
            qty_pcs = qty_gram / grams_per_pc
            cost = qty_pcs * price
            shopping.append({"product": product, "qty_gram": qty_gram,
                             "qty": qty_pcs, "unit": "pcs", "price": price,
                             "cost": round(cost, 2), "warning": None})
        week_total_shop += cost

    # Печать
    print("=" * 78)
    print("PREMIUM-ВЕРСИЯ — ТОЧНЫЙ ПЕРЕСЧЁТ (v3, прямые цены ₽/кг и ₽/шт)")
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
                          f"× {r['unit_price']:>7.2f} ₽/кг = {r['cost']:6.2f} ₽")
                elif r["unit"] == "pcs":
                    grams_per_pc = PIECE_GRAMS.get(r["product"].strip().lower(),
                                                   PIECE_GRAMS.get(normalize(r["product"]), 50.0))
                    pcs = r["qty_gram"] / grams_per_pc
                    print(f"      - {r['product']:<30} {r['qty_gram']:>6} г "
                          f"({pcs:.2f} шт) × {r['unit_price']:>5.2f} ₽/шт "
                          f"= {r['cost']:6.2f} ₽")
                elif r["unit"] == "ml":
                    print(f"      - {r['product']:<30} {r['qty_gram']:>6} г "
                          f"({r['qty_gram']:.1f} мл) × {r['unit_price']:>5.2f} ₽/мл "
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
    print(f"{'№':>3}  {'Продукт':<32} {'Кол-во':>12} {'Цена/ед':>10} {'Стоимость':>10}")
    for i, s in enumerate(shopping, 1):
        if s["cost"] is None:
            print(f"{i:>3}  {s['product']:<32} {'':>12} {'':>10} {s['warning']:>10}")
        else:
            if s["unit"] == "kg":
                qty_disp = f"{s['qty']:.3f} кг"
            elif s["unit"] == "pcs":
                qty_disp = f"{s['qty']:.2f} шт"
            elif s["unit"] == "ml":
                qty_disp = f"{s['qty']:.1f} мл"
            else:
                qty_disp = "набор"
            print(f"{i:>3}  {s['product']:<32} {qty_disp:>12} "
                  f"{s['price']:>8.2f}   {s['cost']:>8.2f} ₽")
    print("-" * 78)
    print(f"  ИТОГО ЗА НЕДЕЛЮ (по списку покупок): {week_total_shop:.2f} ₽")
    print("=" * 78)
    print(f"  Расхождение сумм: {abs(week_total_meals - week_total_shop):.2f} ₽")

    # Обновляем JSON
    for day_idx, day in enumerate(plan["days"]):
        plan["days"][day_idx]["total_price_rub"] = days[day_idx]["day_total"]
        for meal_idx, meal in enumerate(day["meals"]):
            plan["days"][day_idx]["meals"][meal_idx]["price_rub"] = days[day_idx]["meals"][meal_idx]["total"]
            for ing_idx, ing in enumerate(meal["ingredients"]):
                r = days[day_idx]["meals"][meal_idx]["rows"][ing_idx]
                if r["cost"] is not None:
                    plan["days"][day_idx]["meals"][meal_idx]["ingredients"][ing_idx]["cost_rub"] = r["cost"]

    plan["meta"]["version"] = "3.0 (точный пересчёт по прямым ценам ₽/кг и ₽/шт)"
    plan["meta"]["recalculated_at"] = "2026-08-16"
    plan["meta"]["recalc_script"] = "reports/recalc_premium_v3.py"
    plan["meta"]["budget_actual_rub_meals"] = round(week_total_meals, 2)
    plan["meta"]["budget_actual_rub_shopping"] = round(week_total_shop, 2)
    plan["total_budget_rub"] = round(week_total_meals, 2)
    plan["total_budget_meals_rub"] = round(week_total_meals, 2)
    plan["total_budget_shopping_rub"] = round(week_total_shop, 2)
    plan["budget_by_day_avg"] = round(week_total_meals / 7, 2)

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

    # Отчёт
    lines = []
    lines.append("# Premium-версия — точный пересчёт (v3)\n")
    lines.append("**Методика:** `Стоимость ингредиента = (qty_gram/1000) × price_per_kg` "
                 "(для штучных: `qty_pcs × price_per_pcs`; для жидкостей: `qty_ml × price_per_ml`).\n\n")
    lines.append("Цены — единый источник истины (см. `PRICE` в `reports/recalc_premium_v3.py`).\n\n")

    lines.append("## Сводка\n")
    lines.append("| Показатель | Сумма |")
    lines.append("|---|---:|")
    lines.append(f"| Сумма по приёмам пищи | **{week_total_meals:.2f} ₽** |")
    lines.append(f"| Сумма по списку покупок | **{week_total_shop:.2f} ₽** |")
    lines.append(f"| Расхождение | {abs(week_total_meals - week_total_shop):.2f} ₽ |")
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
    lines.append("| № | Продукт | Кол-во | Цена ₽/кг,шт,мл | Стоимость (₽) |")
    lines.append("|---:|---|---:|---:|---:|")
    for i, s in enumerate(shopping, 1):
        if s["cost"] is None:
            lines.append(f"| {i} | {s['product']} | — | — | нет цены |")
        else:
            if s["unit"] == "kg":
                qty_disp = f"{s['qty']:.3f} кг"
            elif s["unit"] == "pcs":
                qty_disp = f"{s['qty']:.2f} шт"
            elif s["unit"] == "ml":
                qty_disp = f"{s['qty']:.1f} мл"
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
