import logging
import requests
from typing import Optional, Dict, Any, Union
import json
from .config import AppConfig, load_config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """A simple utility class for sending Telegram notifications to admin chat."""
    
    def __init__(self, config: Optional[AppConfig] = None):
        # Use provided config or load default
        self.config = config or load_config()
        
        # Check if Telegram notification is configured
        self.bot_token = self.config.telegram.bot_token
        self.admin_chat_id = self.config.telegram.admin_chat_id
        
        # Flag to track if notifications are enabled
        self.enabled = bool(self.bot_token and self.admin_chat_id)
        
        if not self.enabled:
            logger.warning("Telegram notifications disabled: missing bot_token or admin_chat_id in config")
        else:
            logger.info(f"Telegram notifier initialized. Admin chat ID: {self.admin_chat_id}")
    
    def send_message(self, message: str) -> Dict[str, Any]:
        """Send a message to the admin Telegram chat.
        
        Args:
            message: The text message to send
            
        Returns:
            Dict with status and details about the attempt
        """
        if not self.enabled:
            logger.info(f"Telegram notification skipped (not configured): {message}")
            return {
                "success": False,
                "sent": False,
                "error": "Telegram notifications not configured (missing bot_token or admin_chat_id)",
                "message": message
            }
        
        try:
            # Use Telegram Bot API to send message
            api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.admin_chat_id,
                "text": message,
                "parse_mode": "HTML",  # Allow basic HTML formatting
                "disable_web_page_preview": True
            }
            
            response = requests.post(api_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Telegram notification sent successfully")
                return {
                    "success": True,
                    "sent": True,
                    "message": message
                }
            else:
                error_msg = f"Failed to send Telegram notification. Status: {response.status_code}, Response: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "sent": False,
                    "error": error_msg,
                    "status_code": response.status_code,
                    "message": message
                }
        
        except Exception as e:
            error_msg = f"Error sending Telegram notification: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "sent": False,
                "error": error_msg,
                "message": message
            }
    
    def notify_distribution_start(self, service_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """Send notification about the start of a distribution job.
        
        Args:
            service_name: Name of the service running (e.g., 'bonus', 'demurrage')
            dry_run: Whether this is a dry run
            
        Returns:
            Dict with status of the notification attempt
        """
        run_type = "DRY RUN" if dry_run else "LIVE"
        message = f"🚀 <b>{service_name.upper()} DISTRIBUTION STARTED</b> ({run_type})\n\n"
        message += f"Starting {service_name} airdrop distribution service."
        
        return self.send_message(message)
    
    def notify_distribution_result(self, service_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification about the result of a distribution job.
        
        Args:
            service_name: Name of the service that ran (e.g., 'bonus', 'demurrage')
            result: The result dictionary returned from the service's execute_distribution method
            
        Returns:
            Dict with status of the notification attempt
        """
        status = result.get('status', 'unknown')
        
        if status == 'completed':
            # Successful distribution
            message = f"✅ <b>{service_name.upper()} DISTRIBUTION COMPLETED</b>\n\n"
            
            # Add transaction details
            tx_id = result.get('tx_id', 'Unknown')
            explorer_url = result.get('explorer_url', '')
            recipient_count = result.get('recipient_count', 0)
            
            message += f"Transaction ID: <code>{tx_id}</code>\n"
            if explorer_url:
                message += f"Explorer: {explorer_url}\n"
            message += f"Recipients: {recipient_count}\n"
            
            # Add distribution details if available
            distributions = result.get('distributions', [])
            if distributions:
                message += "\n<b>Distribution Details:</b>\n"
                for dist in distributions:
                    token = dist.get('token', 'Unknown')
                    amount = dist.get('total_distributed', dist.get('total_amount', 0))
                    recipients = dist.get('recipients', 0)
                    amount_str = f"{amount:.8f}" if isinstance(amount, float) else str(amount)
                    message += f"- {token}: {amount_str} to {recipients} recipients\n"
                    
        elif status == 'dry_run':
            # Dry run completed
            message = f"🔍 <b>{service_name.upper()} DRY RUN COMPLETED</b>\n\n"
            
            # Add distribution details
            token_count = result.get('token_count', 0)
            recipient_count = result.get('recipient_count', 0)
            
            message += f"Would distribute to {recipient_count} recipients across {token_count} tokens\n"
            
            # Add details about each token distribution
            distributions = result.get('distributions', [])
            if distributions:
                message += "\n<b>Distribution Details:</b>\n"
                for dist in distributions:
                    token = dist.get('token', 'Unknown')
                    amount_per = dist.get('amount_per', 0)
                    recipients = dist.get('recipients', 0)
                    total_dist = dist.get('total_distributed', 0)
                    amount_per_str = f"{amount_per:.8f}" if isinstance(amount_per, float) else str(amount_per)
                    total_dist_str = f"{total_dist:.8f}" if isinstance(total_dist, float) else str(total_dist)
                    message += f"- {token}: {amount_per_str} each to {recipients} recipients (Total: {total_dist_str})\n"
                    
        else:
            # Failed distribution
            message = f"❌ <b>{service_name.upper()} DISTRIBUTION FAILED</b>\n\n"
            
            # Add error details
            error_msg = result.get('error', 'Unknown error')
            custom_msg = result.get('message', '')
            
            if custom_msg:
                message += f"Error: {custom_msg}\n"
            else:
                message += f"Error: {error_msg}\n"
        
        return self.send_message(message)

# Easy-to-use functions for code that doesn't need the full class
def send_admin_notification(message: str, config: Optional[AppConfig] = None) -> Dict[str, Any]:
    """Simple utility function to send admin notification without creating a TelegramNotifier instance.
    
    Args:
        message: The message to send
        config: Optional AppConfig (will load default if not provided)
        
    Returns:
        Dict with status information
    """
    notifier = TelegramNotifier(config)
    return notifier.send_message(message)

def notify_job_start(service_name: str, dry_run: bool = False, config: Optional[AppConfig] = None) -> Dict[str, Any]:
    """Notify admins that a distribution job is starting.
    
    Args:
        service_name: The name of the service (e.g., 'bonus', 'demurrage')
        dry_run: Whether this is a dry run
        config: Optional AppConfig (will load default if not provided)
        
    Returns:
        Dict with status information
    """
    notifier = TelegramNotifier(config)
    return notifier.notify_distribution_start(service_name, dry_run)

def notify_job_result(service_name: str, result: Dict[str, Any], config: Optional[AppConfig] = None) -> Dict[str, Any]:
    """Notify admins about the result of a distribution job.
    
    Args:
        service_name: The name of the service (e.g., 'bonus', 'demurrage')
        result: The result dictionary from execute_distribution
        config: Optional AppConfig (will load default if not provided)
        
    Returns:
        Dict with status information
    """
    notifier = TelegramNotifier(config)
    return notifier.notify_distribution_result(service_name, result)

# --- New function for Admin Test Summaries ---

def send_admin_test_summary(summary_message: str) -> Dict[str, Any]:
    """Sends a summary message specifically to the admin test summary chat.
    
    Uses ADMIN_TELEGRAM_BOT_TOKEN and ADMIN_TELEGRAM_CHAT_ID from config.
    
    Args:
        summary_message: The text message to send.
        
    Returns:
        Dict with status information about the send attempt.
    """
    try:
        # Load config to get admin credentials (service_type doesn't matter here)
        config = load_config()
        admin_token = config.telegram.admin_bot_token
        admin_chat = config.telegram.admin_summary_chat_id
        
        if not admin_token or not admin_chat:
            logger.warning("Admin test summary notifications disabled: missing ADMIN_TELEGRAM_BOT_TOKEN or ADMIN_TELEGRAM_CHAT_ID in config")
            return {
                "success": False,
                "sent": False,
                "error": "Admin test summary notifications not configured.",
                "message": summary_message
            }
            
        logger.info(f"Sending admin test summary notification to chat ID: {admin_chat}")
        
        # Use Telegram Bot API to send message
        api_url = f"https://api.telegram.org/bot{admin_token}/sendMessage"
        
        payload = {
            "chat_id": admin_chat,
            "text": summary_message,
            "parse_mode": "HTML", # Use HTML for simple formatting
            "disable_web_page_preview": True
        }
        
        response = requests.post(api_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("Admin test summary notification sent successfully")
            return {
                "success": True,
                "sent": True,
                "message": summary_message
            }
        else:
            error_msg = f"Failed to send admin test summary notification. Status: {response.status_code}, Response: {response.text}"
            logger.error(error_msg)
            return {
                "success": False,
                "sent": False,
                "error": error_msg,
                "status_code": response.status_code,
                "message": summary_message
            }
            
    except Exception as e:
        error_msg = f"Error sending admin test summary notification: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "sent": False,
            "error": error_msg,
            "message": summary_message
        } 