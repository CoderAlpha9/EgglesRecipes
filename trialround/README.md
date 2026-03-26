# EgglesRecipes - Trial Round
- Contains code for the emerald and tomatoes trading
- Tried vibecoding [PNL=700 to 800]: Mean reversion for emerald and ema for tomatoes

## Codes in bots directory
- datamodel = dependency
- example = from wiki
- gemini_vibecoded_jk_1 [PNL 700] uses mean reversion for emerald to buy below and sell above, tomoatoes uses mean band limit orders to fill max capacity of 80 
- gemini_vibecoded_jk_2 [PNL 800]: Emerald (skew to offload, mean reversion sniping) + Tomatoes (0.2 alpha ema - stored serially in traderData) + Overall partial market making for liquid positions
- gemini_vibecoded_jk_3 [PNL -4186 = BAD]: Built on gemini varn 2 above but with more metrics like vwap, obi, etc [descr to be updated]