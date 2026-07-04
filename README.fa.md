# orbo

**کتابخانه Python برای دسترسی به داده‌های بورس تهران (TSETMC)**

فارسی | [English](README.md)

---

`orbo` دسترسی تمیز، typed، و Pandas-friendly به تمام فیدهای عمومی [TSETMC](https://www.tsetmc.com) رو فراهم می‌کنه:
تاریخچه روزانه OHLCV، ریزمعاملات داخل روز، استریم اردربوک، زنجیره آپشن، شاخص‌های بازار، جریان حقیقی/حقوقی، و داده لحظه‌ای — همه با تاریخ شمسی، تعدیل قیمت داخلی، و retry خودکار.

```python
import orbo

# جستجو و دریافت تاریخچه
stock = orbo.Instrument("شپنا")
df    = stock.history(adjust=True)     # OHLCV تعدیل‌شده با تاریخ شمسی
stats = stock.stats()                  # بازده، کجی، کشیدگی، نوع دُم توزیع

# جریان سفارش داخل روز
session    = stock.intraday("20260628")
classified = orbo.TradeSideEngine().classify(session.trades, session.orderbook)
footprint  = orbo.FootprintEngine().build(classified)
print(footprint.summary())             # POC، دلتا، درصد خرید، درصد طبقه‌بندی‌شده

# اسنپشات لحظه‌ای
snap = stock.live()
print(snap.price[["close","last_price","time"]])
print(snap.orderbook)                  # اردربوک ۵ سطحی لحظه‌ای

# زنجیره آپشن
chain = orbo.OptionChain.fetch()
df    = chain.for_expiry("اهرم", "1405-04-31")

# شاخص بازار
idx = orbo.find_index("شاخص كل")
df  = idx.history()
```

---

## نصب

```bash
pip install orbo
```

**نیاز به Python ≥ 3.11**

وابستگی‌ها: `httpx`, `pandas`, `pydantic`, `jdatetime`, `pyarrow`

> **نکته:** آدرس API مورد استفاده (`cdn.tsetmc.com`) از داخل ایران مستقیم در دسترسه. از خارج از ایران به VPN با IP داخلی نیاز دارید.

---

## شروع سریع

### ۱ — تاریخچه قیمت روزانه

```python
import orbo

stock = orbo.Instrument("فملی")        # جستجو با نماد
df    = stock.history()                # تاریخچه کامل OHLCV با تاریخ شمسی
df    = stock.history(adjust=True)     # تعدیل‌شده (سود نقدی + افزایش سرمایه)
df    = stock.history(count=30)        # ۳۰ روز معاملاتی اخیر

print(df[["date","close","volume"]].tail())
```

### ۲ — آمار توصیفی و توزیع بازده

```python
stats = stock.stats(adjust=True)

print(stats.descriptive)              # میانگین، میانه، انحراف معیار، دامنه
print(stats.distribution)            # کجی، کشیدگی، نوع دُم، آیا fat-tail هست
print(stats.monthly)                 # بازده ماهانه مرکب
print(stats.yearly)                  # بازده سالانه مرکب
print(stats.cumulative.iloc[-1])     # بازده تجمعی کل دوره
print(stats.nav_index)               # اندیس NAV با شروع از ۱۰۰
```

### ۳ — ریزمعاملات و داده داخل روز

```python
session  = stock.intraday("20260628")

df_trades = session.trades           # ریزمعاملات مرتب‌شده بر اساس شماره معامله
df_ob     = session.orderbook        # استریم آپدیت اردربوک (incremental)
df_pt     = session.price_tape       # نوار قیمت پایانی رسمی
df_ct     = session.client_type      # جریان خرید/فروش حقیقی-حقوقی
df_sh     = session.shareholders     # سهامداران عمده
```

### ۴ — تشخیص طرف تهاجمی (Lee-Ready)

```python
classified = orbo.TradeSideEngine().classify(
    session.trades,
    session.orderbook,    # Quote Rule را فعال می‌کند؛ در غیر این صورت Tick Rule
)
# هر ردیف دو ستون اضافه می‌گیرد:
# side: "buy" | "sell" | "unknown"
# method: "quote" | "tick" | "tick_carry"
```

### ۵ — داده چارت Footprint

```python
result = orbo.FootprintEngine().build(classified)

print(result.poc_price)      # Point of Control — پرمعامله‌ترین قیمت
print(result.total_delta)    # فشار خرید خالص جلسه
print(result.bars)           # جزئیات هر سطح قیمتی: خرید، فروش، دلتا، عدم‌تعادل
```

### ۶ — زنجیره آپشن

```python
chain = orbo.OptionChain.fetch()           # همه بازارها
chain = orbo.OptionChain.fetch(1)          # فقط بورس

print(chain.underlyings)                   # لیست دارایی‌های پایه
df = chain.for_expiry("اهرم", "1405-04-31")   # جدول اعمال یک سررسید
print(chain.summary())                     # تعداد اعمال، OI کل به تفکیک سررسید

chain.refresh()                            # دریافت مجدد قیمت‌های لحظه‌ای
```

### ۷ — شاخص‌های بازار

```python
# اسنپشات همه شاخص‌ها
df = orbo.index_snapshot()

# یک شاخص با جستجوی نام
idx = orbo.find_index("شاخص كل")
df  = idx.history()          # تاریخچه کامل روزانه با تاریخ شمسی
df  = idx.today()            # سری زمانی داخل روز امروز
df  = idx.companies()        # شرکت‌های عضو با قیمت لحظه‌ای

# آمار روی تاریخچه شاخص
stats = idx.stats()
```

### ۸ — داده لحظه‌ای

```python
snap = orbo.Instrument("شپنا").live()   # ۴ endpoint با یک اتصال

snap.price        # قیمت لحظه‌ای جلسه جاری (همان schema که today() برمی‌گردانه)
snap.trades       # همه معاملات تا همین لحظه امروز
snap.orderbook    # اسنپشات کامل ۵ سطحی (نه incremental)
snap.client_type  # جریان حقیقی/حقوقی جلسه جاری
```

### ۹ — دریافت دسته‌ای چند روزه با retry

```python
sessions, failed = orbo.fetch_intraday_range(
    inscode = "7745894403636165",
    dates   = ["20260622", "20260623", "20260624", "20260625"],
    fields  = ["trades", "orderbook"],
)
if failed:
    print("روزهای ناموفق:", failed)
```

---

## معماری

```
orbo/
├── clients/        لایه HTTP — wrapper های httpx با retry خودکار
├── data/           transformerها — JSON خام → DataFrame typed
├── engines/        محاسبات خالص — بدون شبکه، بدون I/O
│   ├── adjustment.py   تعدیل تجمعی قیمت
│   ├── trade_side.py   طبقه‌بندی طرف تهاجمی (Quote + Tick Rule)
│   ├── footprint.py    تجمیع خرید/فروش به تفکیک سطح قیمتی
│   ├── daily_stats.py  سری بازده + آمار توزیع
│   └── intra_stats.py  VWAP داخل روز + توزیع
├── models/         آبجکت‌های Pydantic
├── registry/       جستجوی محلی نماد (کش Parquet)
├── history/        InstrumentHistory — OHLCV روزانه
├── intraday/       IntradaySession — داده tick هر روز
├── index/          MarketIndex — شاخص‌های TSE/OTC
├── option_chain/   OptionChain — قراردادهای آپشن لیست‌شده
└── instrument.py   Instrument — API یکپارچه سطح بالا
```

**اصول طراحی:**
- Engine‌ها توابع خالص روی DataFrame هستند — بدون شبکه، بدون فایل، کاملاً قابل تست.
- Transformer‌ها مالک تمام تغییر نام فیلدها و تبدیل تاریخ به شمسی هستند.
- هر HTTP client به‌صورت خودکار retry می‌کند (۳ بار، backoff نمایی).
- `insCode` و `dEven` وقتی از API برگشته‌اند به صورت null قابل اعتماد نیستند — caller آن‌ها را تزریق می‌کند.

---

## endpointهای پشتیبانی‌شده

| دسته | Endpoint | متد orbo |
|---|---|---|
| OHLCV روزانه | GetClosingPriceDailyList | `stock.history()` |
| قیمت لحظه‌ای | GetClosingPriceInfo | `stock.today()`, `stock.live().price` |
| تعدیل قیمت | GetPriceAdjustList | `stock.history(adjust=True)` |
| افزایش سرمایه | GetInstrumentShareChange | `stock.history(adjust=True)` |
| ریزمعاملات | GetTradeHistory | `session.trades` |
| معاملات لحظه‌ای | GetTrade | `stock.live().trades` |
| اردربوک (تاریخی) | BestLimits/{date} | `session.orderbook` |
| اردربوک (لحظه‌ای) | BestLimits | `stock.live().orderbook` |
| نوار قیمت | GetClosingPriceHistory | `session.price_tape` |
| حقیقی/حقوقی (تاریخی) | GetClientTypeHistory | `session.client_type` |
| حقیقی/حقوقی (لحظه‌ای) | GetClientType | `stock.live().client_type` |
| سهامداران | Shareholder | `session.shareholders` |
| وضعیت معاملاتی | GetInstrumentStateAll | `stock.state()` |
| زنجیره آپشن | GetInstrumentOptionMarketWatch | `OptionChain.fetch()` |
| اسنپشات شاخص | GetIndexB1LastAll | `orbo.index_snapshot()` |
| تاریخچه شاخص | GetIndexB2History | `idx.history()` |
| شاخص داخل روز | GetIndexB1LastDay | `idx.today()` |
| شرکت‌های شاخص | GetIndexCompany | `idx.companies()` |
| جستجوی نماد | GetInstrumentSearch | `orbo.search("فملی")` |

---

## آینده

**`orbo-quant`** — کتابخانه‌ای جدا که از `orbo` داده می‌خواند و موارد زیر را اضافه می‌کند:

- قیمت‌گذاری Black-Scholes و Greeks (Δ, Γ, Θ, Vega, Rho)
- حل‌کننده Implied Volatility
- ساخت سطح IV
- سازنده استراتژی آپشن و دیاگرام P&L
- بهینه‌سازی پورتفولیو

`orbo` به دریافت داده اختصاص دارد. تحلیل در `orbo-quant` قرار می‌گیرد.

---

## توسعه

```bash
git clone https://github.com/your-username/orbo
cd orbo
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

---

## مجوز

MIT © 2026
