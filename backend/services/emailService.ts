import * as nodemailer from 'nodemailer';

interface EmailTemplate {
  to: string;
  subject: string;
  html: string;
}

class EmailService {
  private from = 'Mapletenders <hello@kennethwong.ai>';
  private transporter: nodemailer.Transporter;

  constructor() {
    this.transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      port: Number(process.env.SMTP_PORT) || 465,
      secure: true,
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASSWORD,
      },
    });
  }

  private async send(to: string, subject: string, html: string) {
    await this.transporter.sendMail({
      from: this.from,
      to,
      subject,
      html,
    });
  }

  async sendWelcomeEmail(userEmail: string, userName: string): Promise<void> {
    const template = this.getWelcomeEmailTemplate(userName);

    try {
      await this.send(userEmail, template.subject, template.html);
      console.log('Welcome email sent successfully to:', userEmail);
    } catch (error) {
      console.error('Failed to send welcome email:', error);
      throw error;
    }
  }

  async sendPasswordResetEmail(userEmail: string, resetLink: string): Promise<void> {
    const template = this.getPasswordResetEmailTemplate(resetLink);

    try {
      await this.send(userEmail, template.subject, template.html);
      console.log('Password reset email sent successfully to:', userEmail);
    } catch (error) {
      console.error('Failed to send password reset email:', error);
      throw error;
    }
  }

  async sendSubscriptionConfirmationEmail(
    userEmail: string,
    userName: string,
    planName: string,
    billingCycle: string,
    amount: number
  ): Promise<void> {
    const template = this.getSubscriptionConfirmationTemplate(userName, planName, billingCycle, amount);

    try {
      await this.send(userEmail, template.subject, template.html);
      console.log('Subscription confirmation email sent successfully to:', userEmail);
    } catch (error) {
      console.error('Failed to send subscription confirmation email:', error);
      throw error;
    }
  }

  async sendInvoiceEmail(
    userEmail: string,
    userName: string,
    invoiceUrl: string,
    amount: number,
    invoiceNumber: string
  ): Promise<void> {
    const template = this.getInvoiceEmailTemplate(userName, invoiceUrl, amount, invoiceNumber);

    try {
      await this.send(userEmail, template.subject, template.html);
      console.log('Invoice email sent successfully to:', userEmail);
    } catch (error) {
      console.error('Failed to send invoice email:', error);
      throw error;
    }
  }

  private getWelcomeEmailTemplate(userName: string): EmailTemplate {
    return {
      to: '',
      subject: 'Welcome to Mapletenders - Your Procurement Intelligence Journey Begins!',
      html: `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Welcome to Mapletenders</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #DC2626 0%, #B91C1C 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center; }
            .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }
            .footer { background: #f9fafb; padding: 20px; border-radius: 0 0 8px 8px; text-align: center; font-size: 14px; color: #6b7280; }
            .button { display: inline-block; background: #DC2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 20px 0; }
            .feature { display: flex; align-items: center; margin: 15px 0; }
            .feature-icon { background: #fee2e2; color: #DC2626; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 12px; font-weight: bold; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0; font-size: 28px;">Welcome to Mapletenders!</h1>
              <p style="margin: 10px 0 0 0; opacity: 0.9;">Canada's Premier Procurement Intelligence Platform</p>
            </div>

            <div class="content">
              <h2 style="color: #1f2937; margin-top: 0;">Hi ${userName}!</h2>

              <p>Thank you for joining Mapletenders! You're now part of Canada's leading community of businesses that win more government contracts through intelligent procurement insights.</p>

              <h3 style="color: #DC2626; margin-top: 30px;">Get Started in 3 Simple Steps:</h3>

              <div class="feature">
                <div class="feature-icon">1</div>
                <div>
                  <strong>Complete Your Profile</strong><br>
                  <span style="color: #6b7280;">Tell us about your business to get personalized tender recommendations</span>
                </div>
              </div>

              <div class="feature">
                <div class="feature-icon">2</div>
                <div>
                  <strong>Explore Tender Opportunities</strong><br>
                  <span style="color: #6b7280;">Browse thousands of Canadian government contracts with our AI-powered matching</span>
                </div>
              </div>

              <div class="feature">
                <div class="feature-icon">3</div>
                <div>
                  <strong>Set Up Alerts</strong><br>
                  <span style="color: #6b7280;">Never miss relevant opportunities with custom notifications</span>
                </div>
              </div>

              <div style="text-align: center; margin: 30px 0;">
                <a href="https://tender.kennethwong.ai" class="button">Start Exploring Tenders</a>
              </div>

              <p style="margin-bottom: 0;">Welcome aboard!</p>
              <p style="margin-top: 5px;"><strong>The Mapletenders Team</strong></p>
            </div>

            <div class="footer">
              <p>Mapletenders | Helping Canadian Businesses Win Government Contracts</p>
            </div>
          </div>
        </body>
        </html>
      `
    };
  }

  private getPasswordResetEmailTemplate(resetLink: string): EmailTemplate {
    return {
      to: '',
      subject: 'Reset Your Mapletenders Password',
      html: `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Reset Your Password</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #DC2626; color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center; }
            .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }
            .footer { background: #f9fafb; padding: 20px; border-radius: 0 0 8px 8px; text-align: center; font-size: 14px; color: #6b7280; }
            .button { display: inline-block; background: #DC2626; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 20px 0; }
            .warning { background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 20px; margin: 20px 0; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0; font-size: 24px;">Password Reset Request</h1>
            </div>

            <div class="content">
              <h2 style="color: #1f2937; margin-top: 0;">Reset Your Password</h2>

              <p>We received a request to reset your Mapletenders account password. If you made this request, click the button below to set a new password:</p>

              <div style="text-align: center; margin: 30px 0;">
                <a href="${resetLink}" class="button">Reset My Password</a>
              </div>

              <div class="warning">
                <h4 style="color: #dc2626; margin: 0 0 10px 0;">Important Security Notice</h4>
                <ul style="margin: 0; color: #dc2626;">
                  <li>This link will expire in 1 hour</li>
                  <li>If you didn't request this reset, please ignore this email</li>
                  <li>Never share this link with anyone</li>
                </ul>
              </div>

              <p style="margin-bottom: 0;">Best regards,</p>
              <p style="margin-top: 5px;"><strong>The Mapletenders Team</strong></p>
            </div>

            <div class="footer">
              <p>Mapletenders | <a href="https://tender.kennethwong.ai" style="color: #6b7280;">tender.kennethwong.ai</a></p>
            </div>
          </div>
        </body>
        </html>
      `
    };
  }

  private getSubscriptionConfirmationTemplate(
    userName: string,
    planName: string,
    billingCycle: string,
    amount: number
  ): EmailTemplate {
    return {
      to: '',
      subject: `Welcome to Mapletenders ${planName} - Your Subscription is Active!`,
      html: `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Subscription Confirmation</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #DC2626 0%, #B91C1C 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center; }
            .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }
            .footer { background: #f9fafb; padding: 20px; border-radius: 0 0 8px 8px; text-align: center; font-size: 14px; color: #6b7280; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0; font-size: 28px;">Subscription Confirmed!</h1>
              <p style="margin: 10px 0 0 0; opacity: 0.9;">Welcome to ${planName}</p>
            </div>

            <div class="content">
              <h2 style="color: #1f2937; margin-top: 0;">Hi ${userName}!</h2>
              <p>Your Mapletenders ${planName} subscription is now active.</p>
              <p><strong>Plan:</strong> ${planName} | <strong>Amount:</strong> $${amount} CAD ${billingCycle}</p>

              <p style="margin-bottom: 0;">Happy contracting!</p>
              <p style="margin-top: 5px;"><strong>The Mapletenders Team</strong></p>
            </div>

            <div class="footer">
              <p>Mapletenders | <a href="https://tender.kennethwong.ai" style="color: #6b7280;">tender.kennethwong.ai</a></p>
            </div>
          </div>
        </body>
        </html>
      `
    };
  }

  private getInvoiceEmailTemplate(
    userName: string,
    invoiceUrl: string,
    amount: number,
    invoiceNumber: string
  ): EmailTemplate {
    return {
      to: '',
      subject: `Invoice ${invoiceNumber} from Mapletenders - $${amount} CAD`,
      html: `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Invoice from Mapletenders</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #1f2937; color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center; }
            .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; }
            .footer { background: #f9fafb; padding: 20px; border-radius: 0 0 8px 8px; text-align: center; font-size: 14px; color: #6b7280; }
            .button { display: inline-block; background: #DC2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 20px 0; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0; font-size: 24px;">Invoice from Mapletenders</h1>
              <p style="margin: 10px 0 0 0; opacity: 0.9;">Invoice #${invoiceNumber}</p>
            </div>

            <div class="content">
              <h2 style="color: #1f2937; margin-top: 0;">Hi ${userName}!</h2>
              <p>Your invoice is ready.</p>
              <p><strong>Invoice:</strong> ${invoiceNumber} | <strong>Amount:</strong> $${amount} CAD</p>

              <div style="text-align: center; margin: 30px 0;">
                <a href="${invoiceUrl}" class="button">Download Invoice</a>
              </div>

              <p style="margin-bottom: 0;">Thank you!</p>
              <p style="margin-top: 5px;"><strong>The Mapletenders Team</strong></p>
            </div>

            <div class="footer">
              <p>Mapletenders | <a href="https://tender.kennethwong.ai" style="color: #6b7280;">tender.kennethwong.ai</a></p>
            </div>
          </div>
        </body>
        </html>
      `
    };
  }
}

export default new EmailService();
