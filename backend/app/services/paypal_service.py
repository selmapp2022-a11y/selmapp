from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timedelta
import logging
from python_paypal_api.api import Orders, Transactions
from python_paypal_api.base import PaypalApiException
from app.core.config import settings

logger = logging.getLogger(__name__)


class PayPalService:
    """Modern PayPal service using python-paypal-api"""
    
    def __init__(self):
        self._orders_api = None
        self._transactions_api = None
        self._credentials = None
        
    def _ensure_initialized(self):
        """Ensure PayPal APIs are initialized with credentials"""
        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
            raise Exception("PayPal credentials not configured. Please set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in your environment.")
        
        if self._orders_api is None:
            self._credentials = {
                "client_id": settings.PAYPAL_CLIENT_ID,
                "client_secret": settings.PAYPAL_CLIENT_SECRET,
                "client_mode": "PRODUCTION" if settings.PAYPAL_MODE == "live" else "SANDBOX"
            }
            
            # Initialize API clients
            self._orders_api = Orders(credentials=self._credentials)
            self._transactions_api = Transactions(credentials=self._credentials)
    
    @property
    def orders_api(self):
        self._ensure_initialized()
        return self._orders_api
    
    @property
    def transactions_api(self):
        self._ensure_initialized()
        return self._transactions_api
    
    async def create_order(
        self, 
        amount: Decimal, 
        currency: str = "USD", 
        description: str = "SelmApp Payment",
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a PayPal order for one-time payment"""
        try:
            order_data = {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "amount": {
                            "currency_code": currency,
                            "value": str(amount)
                        },
                        "description": description
                    }
                ],
                "application_context": {
                    "return_url": return_url or settings.PAYMENT_SUCCESS_URL,
                    "cancel_url": cancel_url or settings.PAYMENT_CANCEL_URL,
                    "brand_name": "SelmApp",
                    "landing_page": "BILLING",
                    "shipping_preference": "NO_SHIPPING",
                    "user_action": "PAY_NOW"
                }
            }
            
            response = self.orders_api.create_order(order_data)
            
            # Extract approval URL
            approval_url = None
            if "links" in response:
                for link in response["links"]:
                    if link["rel"] == "approve":
                        approval_url = link["href"]
                        break
            
            return {
                "order_id": response["id"],
                "status": response["status"],
                "approval_url": approval_url,
                "response": response
            }
            
        except PaypalApiException as e:
            logger.error(f"PayPal order creation failed: {e}")
            raise Exception(f"PayPal order creation failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating PayPal order: {e}")
            raise Exception(f"Failed to create PayPal order: {str(e)}")
    
    async def capture_order(self, order_id: str) -> Dict[str, Any]:
        """Capture a PayPal order"""
        try:
            response = self.orders_api.capture_order(order_id)
            
            # Extract capture details
            capture_info = {
                "order_id": order_id,
                "status": response["status"],
                "capture_id": None,
                "payer_id": None,
                "amount": None,
                "currency": None
            }
            
            if "purchase_units" in response:
                for unit in response["purchase_units"]:
                    if "payments" in unit and "captures" in unit["payments"]:
                        for capture in unit["payments"]["captures"]:
                            capture_info["capture_id"] = capture["id"]
                            capture_info["amount"] = capture["amount"]["value"]
                            capture_info["currency"] = capture["amount"]["currency_code"]
                            break
            
            if "payer" in response:
                capture_info["payer_id"] = response["payer"]["payer_id"]
            
            return capture_info
            
        except PaypalApiException as e:
            logger.error(f"PayPal order capture failed: {e}")
            raise Exception(f"PayPal order capture failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error capturing PayPal order: {e}")
            raise Exception(f"Failed to capture PayPal order: {str(e)}")
    
    async def get_order_details(self, order_id: str) -> Dict[str, Any]:
        """Get PayPal order details"""
        try:
            response = self.orders_api.get_order(order_id)
            return response
            
        except PaypalApiException as e:
            logger.error(f"Failed to get PayPal order details: {e}")
            raise Exception(f"Failed to get PayPal order details: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting PayPal order: {e}")
            raise Exception(f"Failed to get PayPal order: {str(e)}")
    
    async def create_subscription_plan(
        self, 
        name: str, 
        description: str,
        amount: Decimal,
        currency: str = "USD",
        billing_cycle: str = "monthly"
    ) -> Dict[str, Any]:
        """Create a PayPal subscription plan using REST API"""
        try:
            # Use PayPal REST SDK for subscription plans
            import paypalrestsdk
            
            # Configure PayPal SDK
            paypalrestsdk.configure({
                "mode": settings.PAYPAL_MODE,  # sandbox or live
                "client_id": settings.PAYPAL_CLIENT_ID,
                "client_secret": settings.PAYPAL_CLIENT_SECRET
            })
            
            # Define billing plan
            billing_plan = paypalrestsdk.BillingPlan({
                "name": name,
                "description": description,
                "type": "INFINITE",
                "payment_definitions": [{
                    "name": f"{billing_cycle.title()} Payment",
                    "type": "REGULAR",
                    "frequency": "MONTH" if billing_cycle == "monthly" else "YEAR",
                    "frequency_interval": "1",
                    "amount": {
                        "value": str(amount),
                        "currency": currency
                    },
                    "cycles": "0"  # Infinite cycles
                }],
                "merchant_preferences": {
                    "setup_fee": {
                        "value": "0",
                        "currency": currency
                    },
                    "return_url": settings.PAYMENT_SUCCESS_URL,
                    "cancel_url": settings.PAYMENT_CANCEL_URL,
                    "auto_bill_amount": "YES",
                    "initial_fail_amount_action": "CONTINUE",
                    "max_fail_attempts": "3"
                }
            })
            
            # Create the billing plan
            if billing_plan.create():
                # Activate the plan
                patch = [{
                    "op": "replace",
                    "path": "/",
                    "value": {
                        "state": "ACTIVE"
                    }
                }]
                
                if billing_plan.replace(patch):
                    logger.info(f"Created and activated PayPal billing plan: {billing_plan.id}")
                    return {
                        "id": billing_plan.id,
                        "name": name,
                        "description": description,
                        "status": "ACTIVE",
                        "amount": str(amount),
                        "currency": currency,
                        "billing_cycle": billing_cycle
                    }
                else:
                    logger.error(f"Failed to activate PayPal billing plan: {billing_plan.error}")
                    raise Exception(f"Failed to activate billing plan: {billing_plan.error}")
            else:
                logger.error(f"Failed to create PayPal billing plan: {billing_plan.error}")
                raise Exception(f"Failed to create billing plan: {billing_plan.error}")
                
        except Exception as e:
            logger.error(f"PayPal subscription plan creation failed: {e}")
            raise Exception(f"Failed to create subscription plan: {str(e)}")
    
    async def create_subscription(
        self, 
        plan_id: str,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a PayPal subscription using REST API"""
        try:
            import paypalrestsdk
            
            # Configure PayPal SDK
            paypalrestsdk.configure({
                "mode": settings.PAYPAL_MODE,
                "client_id": settings.PAYPAL_CLIENT_ID,
                "client_secret": settings.PAYPAL_CLIENT_SECRET
            })
            
            # Create billing agreement
            billing_agreement = paypalrestsdk.BillingAgreement({
                "name": "SelmApp Premium Subscription",
                "description": "SelmApp Premium subscription agreement",
                "start_date": (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "plan": {
                    "id": plan_id
                },
                "payer": {
                    "payment_method": "paypal"
                }
            })
            
            if billing_agreement.create():
                # Get approval URL
                approval_url = None
                for link in billing_agreement.links:
                    if link.rel == "approval_url":
                        approval_url = link.href
                        break
                
                logger.info(f"Created PayPal billing agreement: {billing_agreement.token}")
                return {
                    "subscription_id": billing_agreement.token,
                    "status": "APPROVAL_PENDING",
                    "approval_url": approval_url,
                    "agreement_token": billing_agreement.token
                }
            else:
                logger.error(f"Failed to create PayPal billing agreement: {billing_agreement.error}")
                raise Exception(f"Failed to create subscription: {billing_agreement.error}")
                
        except Exception as e:
            logger.error(f"PayPal subscription creation failed: {e}")
            raise Exception(f"Failed to create subscription: {str(e)}")
    
    async def get_subscription_details(self, subscription_id: str) -> Dict[str, Any]:
        """Get PayPal subscription details (placeholder for now)"""
        logger.warning("Get subscription details not implemented - using mock response")
        
        return {
            "id": subscription_id,
            "status": "ACTIVE",
            "plan_id": "PLAN_BASIC_MONTHLY"
        }
    
    async def cancel_subscription(
        self, 
        subscription_id: str, 
        reason: str = "User requested cancellation"
    ) -> Dict[str, Any]:
        """Cancel a PayPal subscription (placeholder for now)"""
        logger.warning("Subscription cancellation not implemented - using mock response")
        
        return {
            "status": "cancelled",
            "response": {"id": subscription_id, "status": "CANCELLED"}
        }
    
    async def create_refund(
        self, 
        capture_id: str, 
        amount: Optional[Decimal] = None,
        currency: str = "USD",
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a PayPal refund (placeholder for now)"""
        # Note: This would require the Payments API which is not available
        # in the current python-paypal-api package. For now, return a mock response
        logger.warning("Refund creation not implemented - using mock response")
        
        return {
            "refund_id": f"REFUND_{capture_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "status": "COMPLETED",
            "amount": str(amount) if amount else "0.00",
            "currency": currency
        }
    
    async def verify_webhook_signature(
        self, 
        webhook_id: str, 
        headers: Dict[str, str], 
        body: str
    ) -> bool:
        """Verify PayPal webhook signature (placeholder for now)"""
        # Note: This would require the Webhooks API which is not available
        # in the current python-paypal-api package. For now, return True
        logger.warning("Webhook signature verification not implemented - returning True")
        return True
    
    async def get_payment_history(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get PayPal payment history (placeholder for now)"""
        logger.warning("Payment history retrieval not implemented - returning empty list")
        return []
    
    def get_webhook_event_types(self) -> List[str]:
        """Get supported PayPal webhook event types"""
        return [
            "PAYMENT.CAPTURE.COMPLETED",
            "PAYMENT.CAPTURE.DENIED",
            "PAYMENT.CAPTURE.REFUNDED",
            "BILLING.SUBSCRIPTION.CREATED",
            "BILLING.SUBSCRIPTION.ACTIVATED",
            "BILLING.SUBSCRIPTION.CANCELLED",
            "BILLING.SUBSCRIPTION.SUSPENDED",
            "BILLING.SUBSCRIPTION.PAYMENT.FAILED"
        ]


# Create a singleton instance
paypal_service = PayPalService() 