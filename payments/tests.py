import base64
import time

MERCHANT_ID = "694d35331922c3549c145482"
amount_sum = 5000
amount_tiyin = amount_sum * 100
order_id = f"TEST-{int(time.time())}"

params = f"m={MERCHANT_ID};ac.order_id={order_id};a={amount_tiyin}"
encoded = base64.b64encode(params.encode()).decode()
payme_url = f"https://checkout.paycom.uz/{encoded}?test=true"

print(payme_url)
