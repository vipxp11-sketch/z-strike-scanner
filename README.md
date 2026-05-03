# Z-Sweep Market Scanner V3

سكانر خارجي مبني على نظام:
- Liquidity Sweep
- Close%
- Volume
- Prev Candle
- Impulse
- Wave Phase
- Bias من الشهري/الأسبوعي/اليومي

## التشغيل

```bash
pip install -r requirements.txt
streamlit run app.py
```

## القواعد

CALL:
- Bias CALL
- Sweep أدنى
- Prev Candle أحمر
- Close% >= 70
- Volume أعلى من الشمعة السابقة
- Wave ① أو ②

PUT:
- Bias PUT
- Sweep أعلى
- Prev Candle أخضر
- Close% <= 30
- Volume أعلى من الشمعة السابقة
- Wave ① أو ②

## ملاحظة
مصدر البيانات في هذه النسخة هو yfinance، مناسب للتجربة وليس الأفضل للسكالبينج اللحظي عالي الدقة.
