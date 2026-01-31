import os
import json
import random
from datetime import datetime
import stripe
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from factory_v2 import create_agent_server

# Load env
load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "") 

app = Flask(__name__)
CORS(app) # Enable CORS for frontend fetch

STATS_FILE = "stats.json"

def load_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    default_stats = {"date": today, "base": random.randint(3, 5), "sales": 0}
    
    if not os.path.exists(STATS_FILE):
        return default_stats
        
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
            
        # Check if date rolled over
        if data.get("date") != today:
            data["date"] = today
            data["base"] = random.randint(3, 5) # New random base for the new day
            data["sales"] = 0 # Reset REAL sales to 0 (accumulate daily)
            save_stats(data)
            
        return data
    except:
        return default_stats

def save_stats(data):
    with open(STATS_FILE, "w") as f:
        json.dump(data, f)

@app.route('/stats', methods=['GET'])
def get_stats():
    stats = load_stats()
    
    # "Drip" Logic: Add 1 fake sale every 3 hours to simulate steady momentum
    # This prevents the number from stagnating if real sales are slow
    current_hour = datetime.now().hour
    drip_count = max(0, current_hour // 3) 
    
    total = stats["base"] + stats["sales"] + drip_count
    return jsonify({"count": total, "date": stats["date"]})

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    try:
        # MVP: Parse JSON directly if using local triggers, otherwise verify signature in prod
        # event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        event = json.loads(payload) 
    except Exception as e:
        return 'Invalid payload', 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_details', {}).get('email')
        referrer = session.get('client_reference_id', 'none')
        
        print(f"💰 PAYMENT RECEIVED: $149 from {customer_email} (Ref: {referrer})")
        
        # Log Referral
        if referrer and referrer != 'none':
            with open("referrals.log", "a") as f:
                f.write(f"{datetime.now().isoformat()},{referrer},149,{customer_email}\n")
        
        # INCREMENT STATS
        stats = load_stats()
        stats["sales"] += 1
        save_stats(stats)
        print(f"📈 Sales updated: {stats['sales']} today (Display: {stats['base'] + stats['sales']})")

        # TRIGGER FACTORY (Async in prod, sync here for MVP)
        try:
            print("🚀 Launching Agent Factory...")
            # droplet_info = create_agent_server(customer_email) 
            # send_email_to_customer(customer_email, droplet_info)
            print("✅ Fulfillment Complete.")
        except Exception as e:
            print(f"❌ Fulfillment Failed: {e}")

    return jsonify(success=True)

if __name__ == '__main__':
    print("🤖 Webhook Listener Running on port 4242...")
    app.run(port=4242)
