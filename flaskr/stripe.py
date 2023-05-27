from flask import Blueprint, request, jsonify
import stripe

from flaskr.firebase import check_payment_intent_exists, get_transactions, store_payment_intent
from .auth import getUserAppMetadata, require_auth, getUserID
import os
from dotenv import load_dotenv, find_dotenv
from authlib.integrations.flask_oauth2 import current_token

bp = Blueprint("stripe", __name__)

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

stripe.api_key = os.environ['STRIPE_API_TEST']


@bp.route("/add_wallet_credit", methods=["POST"])
@require_auth(None)
def add_wallet_credit():
    amount_in_dollars = request.json['amount']
    amount_in_cents = int(amount_in_dollars) * 100  
    intent_id = request.json.get('intent_id')
    stripe_customer_id = getUserAppMetadata(current_token.get('sub'))['stripe_customer_id']

    if not intent_id:
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_in_cents,
            currency='usd',
            customer=stripe_customer_id,
            description='Add wallet credit'
        )

    else:
        payment_intent = stripe.PaymentIntent.modify(
            intent_id,
            amount=amount_in_cents,
        )

    return jsonify({
    'client_secret': payment_intent.client_secret,
    'registered_amount': payment_intent.amount / 100,
    'intent_id': payment_intent.id,
    })

def get_balance(user_sub):
    stripe_customer_id = getUserAppMetadata(user_sub)['stripe_customer_id']
    customer = stripe.Customer.retrieve(stripe_customer_id)
    return customer.balance

def update_balance(new_balance_cents, user_sub):
    stripe_customer_id = getUserAppMetadata(user_sub)['stripe_customer_id']

    customer = stripe.Customer.modify(
        stripe_customer_id,
        balance=new_balance_cents
    )

    return customer.balance 


@bp.route("/get_customer_balance", methods=["POST"])
@require_auth(None)
def get_customer_balance():
    balance = get_balance(current_token.get('sub'))
    print(balance)
    return jsonify({'balance': balance / 100})


@bp.route("/validate_payment", methods=["POST"])
@require_auth(None)
def validate_payment():
    # get payment intent id from request
    intent_id = request.json['intent_id']
    user_id = getUserID(current_token)
    # check if payment intent is successful
    payment_intent = stripe.PaymentIntent.retrieve(intent_id)
    if payment_intent.status == 'succeeded':
        if check_payment_intent_exists(user_id, intent_id):
            return jsonify({'error': 'Payment already confirmed'})
        else:
            store_payment_intent(user_id, intent_id)
            stripe_customer_id = getUserAppMetadata(current_token.get('sub'))['stripe_customer_id']
            customer = stripe.Customer.retrieve(stripe_customer_id)
            new_balance = customer.balance + payment_intent.amount
            stripe.Customer.modify(stripe_customer_id, balance=new_balance)
            updated_customer = stripe.Customer.retrieve(stripe_customer_id)
            return jsonify({'balance': 'Balance updated successfully! Your new balance is $' + str(updated_customer.balance / 100)})
        
        
@bp.route("/get_customer_transactions", methods=["POST"])
@require_auth(None)
def get_customer_transactions():
    transactions = get_transactions(getUserID(current_token))
    # stripe_customer_id = getUserAppMetadata(current_token.get('sub'))['stripe_customer_id']
    # transactions = stripe.Charge.list(customer=stripe_customer_id)
    # formatted_transactions = []
    # for transaction in transactions:
    #     formatted_transactions.append({
    #         'id': transaction.id,
    #         'amount': '{:.2f}'.format(transaction.amount / 100),
    #         'description': transaction.description,
    #         'created': transaction.created,
    #         # 'status': transaction.status
    #     })

    return jsonify(transactions)
