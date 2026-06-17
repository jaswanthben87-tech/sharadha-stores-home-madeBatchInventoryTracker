import os
import sys

# Ensure backend directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import send_email_alert

def main():
    print("=== Testing Email Notification Routing ===")
    
    # 1. Resolve recipient
    recipient = os.environ.get('ALERT_EMAIL')
    if not recipient:
        recipient = os.environ.get('SMTP_EMAIL')
    if not recipient:
        # Check from local .env manually as app.py does
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(dotenv_path):
            with open(dotenv_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val = parts[1].strip().strip('\"\'')
                            if key == 'ALERT_EMAIL':
                                recipient = val
                            elif key == 'SMTP_EMAIL' and not recipient:
                                recipient = val
                                
    if not recipient:
        recipient = "sharadhastores4@gmail.com"
        
    print(f"Target Recipient: {recipient}")
    
    # Check credentials status
    resend_key = os.environ.get('RESEND_API_KEY')
    brevo_key = os.environ.get('BREVO_API_KEY')
    smtp_email = os.environ.get('SMTP_EMAIL')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    
    # Check from local .env as well
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(dotenv_path):
        with open(dotenv_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().strip('\"\'')
                        if key == 'RESEND_API_KEY' and not resend_key:
                            resend_key = val
                        elif key == 'BREVO_API_KEY' and not brevo_key:
                            brevo_key = val
                        elif key == 'SMTP_EMAIL' and not smtp_email:
                            smtp_email = val
                        elif key == 'SMTP_PASSWORD' and not smtp_password:
                            smtp_password = val

    print(f"Credentials detected:")
    print(f" - RESEND_API_KEY: {'[Configured]' if resend_key else '[Not Configured]'}")
    print(f" - BREVO_API_KEY: {'[Configured]' if brevo_key else '[Not Configured]'}")
    print(f" - SMTP_EMAIL: {'[Configured]' if smtp_email else '[Not Configured]'}")
    print(f" - SMTP_PASSWORD: {'[Configured]' if smtp_password else '[Not Configured]'}")
    
    test_subject = "Sharadha Stores - Alert Verification Test"
    test_text = "Hello! This is a test email sent from the Sharadha Stores Batch Inventory Tracker system to verify email alerting configuration."
    
    test_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; color: #2D3748; line-height: 1.6; padding: 20px; background-color: #F7FAFC;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.02); background-color: #ffffff;">
            <div style="background: linear-gradient(135deg, #4A5568 0%, #2D3748 100%); padding: 25px; text-align: center; color: #ffffff;">
                <h2 style="margin: 0; font-size: 20px; font-weight: 700; letter-spacing: 0.5px;">SYSTEM ALERT TEST</h2>
            </div>
            <div style="padding: 30px;">
                <p style="font-size: 16px; margin: 0 0 20px 0; color: #2D3748;">Hello Administrator,</p>
                <p style="font-size: 16px; margin: 0 0 20px 0; color: #4A5568;">{test_text}</p>
                <div style="background-color: #EDF2F7; border-left: 4px solid #4A5568; padding: 15px; border-radius: 4px; font-family: monospace; font-size: 13px; margin: 20px 0;">
                    Status: Verification in progress...<br>
                    Channel: Email<br>
                    Method: {'Resend API' if resend_key else ('Brevo API' if brevo_key else 'Gmail SMTP Fallback')}
                </div>
            </div>
            <div style="background-color: #EDF2F7; padding: 15px; text-align: center; font-size: 11px; color: #718096; border-top: 1px solid #E2E8F0;">
                Sharadha Stores Homemade Food Product Batch Inventory Tracker.
            </div>
        </div>
    </body>
    </html>
    """
    
    print("\nSending email...")
    send_email_alert(recipient, test_text, test_html)
    print("\nEmail dispatch call completed. Check logs above to verify success.")

if __name__ == "__main__":
    main()
