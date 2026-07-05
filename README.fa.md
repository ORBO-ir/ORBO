<div dir="rtl">

# orbo

**Tehran Stock Exchange data**

[English](README.md) &nbsp;·&nbsp;
[![PyPI](https://img.shields.io/pypi/v/orbo)](https://pypi.org/project/orbo/)
[![Python](https://img.shields.io/pypi/pyversions/orbo)](https://pypi.org/project/orbo/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

`orbo` یک SDK پایتون برای [TSETMC](https://www.tsetmc.com) است.
داده‌های خام API را به DataFrame های تمیز با تاریخ شمسی تبدیل می‌کند —
با تعدیل قیمت، طبقه‌بندی جریان سفارش، و داده لحظه‌ای.

</div>

```python
import orbo

stock = orbo.Instrument("شپنا")

# تاریخچه تعدیل‌شده با تاریخ شمسی
df = stock.history(adjust=True)
#         date      open    high     low   close  volume
# 0  1394-01-05  7,230.0  7,420.0  7,210.0  7,380.0  3.2M
# …
# 1403-11-22   41,250.0  42,100.0  41,100.0  41,900.0  8.7M

# توزیع بازده
stats = stock.stats()
print(stats.descriptive["std"])         # انحراف معیار بازده روزانه
print(stats.distribution["tail_type"])  # fat_tail / thin_tail / normal_tail

# جریان سفارش داخل روز
session    = stock.intraday("20260628")
classified = orbo.TradeSideEngine().classify(session.trades, session.orderbook)
result     = orbo.FootprintEngine().build(classified)
print(result.poc_price)    # Point of Control — پرمعامله‌ترین قیمت روز
print(result.total_delta)  # فشار خرید خالص جلسه
```

<div dir="rtl">

---

## نصب

</div>

```bash
pip install orbo
```

<div dir="rtl">

نیاز به Python نسخه ۳.۱۱ یا بالاتر. از داخل ایران بدون VPN کار می‌کند.

---

## قابلیت‌ها

| متد | توضیح |
|---|---|
| `stock.history(adjust=True)` | تاریخچه کامل OHLCV، تعدیل‌شده برای سود نقدی و افزایش سرمایه |
| `stock.today()` | قیمت لحظه‌ای جلسه جاری |
| `stock.stats()` | بازده روزانه/ماهانه/سالانه، کجی، کشیدگی، نوع دُم توزیع |
| `stock.intraday(date)` | ریزمعاملات، اردربوک، نوار قیمت، سهامداران، جریان حقیقی/حقوقی |
| `stock.live()` | قیمت + معاملات + اردربوک ۵ سطحی + حقیقی/حقوقی — همه با یک اتصال |
| `TradeSideEngine` | طبقه‌بندی طرف تهاجمی به روش Lee-Ready (Quote Rule + Tick Rule) |
| `FootprintEngine` | حجم خرید/فروش، دلتا، POC، و وضعیت عدم‌تعادل — به تفکیک سطح قیمتی |
| `OptionChain.fetch()` | زنجیره کامل آپشن با moneyness — قابل رفرش لحظه‌ای |
| `find_index("شاخص كل")` | شاخص‌های TSE/OTC — تاریخچه، داخل روز، شرکت‌های عضو |

---

## مثال‌ها

### تاریخچه قیمت و آمار

</div>

```python
stock = orbo.Instrument("فملی")
df    = stock.history(adjust=True, count=252)   # یک سال اخیر، تعدیل‌شده

stats = stock.stats(adjust=True)
print(stats.descriptive)   # میانگین، میانه، انحراف معیار، دامنه
print(stats.monthly)       # بازده ماهانه مرکب
print(stats.yearly)        # بازده سالانه مرکب
print(stats.distribution)  # کجی، کشیدگی، طبقه‌بندی fat-tail
print(stats.nav_index)     # اندیس NAV با شروع از ۱۰۰
```

<div dir="rtl">

### جریان سفارش داخل روز ← فوتپرینت

</div>

```python
session = orbo.Instrument("شپنا").intraday("20260628")

# طبقه‌بندی هر معامله به‌عنوان خریدار یا فروشنده تهاجمی
classified = orbo.TradeSideEngine().classify(
    session.trades,
    session.orderbook,   # Quote Rule را فعال می‌کند؛ در غیر این صورت Tick Rule
)

# تجمیع در قالب بارهای فوتپرینت
fp = orbo.FootprintEngine().build(classified)
print(fp.bars[["price","buy_volume","sell_volume","delta","imbalance"]])
print(fp.summary())   # poc_price, total_delta, buy_pct, classified_pct
```

<div dir="rtl">

### زنجیره آپشن

</div>

```python
chain = orbo.OptionChain.fetch()              # اسنپشات کامل، همه بازارها
chain.refresh()                               # آپدیت قیمت‌ها در همان آبجکت

print(chain.underlyings)                      # ["اهرم", "توان", ...]
df = chain.for_expiry("اهرم", "1405-05-31")  # جدول اعمال یک سررسید
print(chain.summary())                        # تعداد اعمال و OI به تفکیک سررسید
```

<div dir="rtl">

### شاخص‌های بازار

</div>

```python
idx = orbo.find_index("شاخص كل")   # جستجو با نام
df  = idx.history()                 # تاریخچه کامل روزانه با تاریخ شمسی

stats = idx.stats()
print(stats.yearly)
```

<div dir="rtl">

### دریافت دسته‌ای با retry خودکار

</div>

```python
sessions, failed = orbo.fetch_intraday_range(
    inscode = "7745894403636165",
    dates   = ["20260622", "20260623", "20260624", "20260625"],
    fields  = ["trades", "orderbook"],
)
# failed ← روزهایی که بعد از همه تلاش‌ها دریافت نشدند
```

<div dir="rtl">

---

## معماری

</div>

```
orbo/
├── clients/        لایه HTTP — retry خودکار روی هر درخواست
├── data/           transformerها — JSON خام → DataFrame typed با تاریخ شمسی
├── engines/        محاسبات خالص — بدون شبکه، کاملاً قابل تست
│   ├── adjustment  تعدیل تجمعی قیمت (backward cumulative pass)
│   ├── trade_side  طبقه‌بندی طرف تهاجمی (Lee-Ready)
│   ├── footprint   تجمیع جریان سفارش به تفکیک سطح قیمتی
│   ├── daily_stats سری بازده + آمار توزیع
│   └── intra_stats VWAP + توزیع سطح tick
├── registry/       کش محلی Parquet برای تبدیل نماد → inscode
└── instrument.py   نقطه ورود یکپارچه سطح بالا
```

<div dir="rtl">

سه قانون طراحی:
- **Engine‌ها** هیچ‌وقت به شبکه دست نمی‌زنند.
- **Transformer‌ها** مسئول تمام تبدیل نام فیلدها و تاریخ شمسی هستند.
- **Client‌ها** به‌صورت خودکار retry می‌کنند (۳ بار، backoff نمایی).

---

## آینده — `orbo-quant`

یک کتابخانه جداگانه که از `orbo` داده می‌خواند و موارد زیر را اضافه می‌کند:

- قیمت‌گذاری Black-Scholes و Greeks — Δ، Γ، Θ، ν، ρ
- حل‌کننده Implied Volatility
- ساخت سطح IV
- سازنده استراتژی آپشن و دیاگرام P&L
- بهینه‌سازی پورتفولیو

`orbo` روی دریافت داده متمرکز می‌ماند. تحلیل در `orbo-quant` قرار می‌گیرد.

---

## توسعه

</div>

```bash
git clone https://github.com/ORBO-ir/ORBO.git
cd ORBO
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

<div dir="rtl">

---

## مجوز

MIT © 2026 — [ORBO-ir](https://github.com/ORBO-ir)

</div>
