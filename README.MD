# 🍽️ Chuks Kitchen — Food Ordering Backend API

> A production-ready REST API backend for a Nigerian food ordering platform, built with Django REST Framework, PostgreSQL, Redis, Celery, and full Paystack payment gateway integration.

---

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [System Requirements](#system-requirements)
- [Environment Setup](#environment-setup)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [API Endpoints](#api-endpoints)
- [Payment Integration](#payment-integration)
- [Running Tests](#running-tests)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## 📖 Project Overview

Chuks Kitchen is a full-featured backend API for a food ordering platform. It handles the complete customer journey — from account registration with OTP email verification, through menu browsing and cart management, to atomic order placement with delivery address capture and Paystack payment processing.

The system is built using **Clean Architecture** principles with a **Service Layer pattern** that keeps business logic separate from HTTP handling. All critical operations run inside atomic database transactions with PostgreSQL row-level locking to prevent race conditions in concurrent order scenarios.

---

## ✨ Features

### User Management
- Register with **email or phone number**
- **OTP email verification** before first login (6-digit code, 10-minute expiry)
- OTP throttling — 60-second cooldown + max 5 requests per hour (Redis-backed)
- **Referral code** system at registration
- JWT authentication with **refresh token rotation** and blacklisting on logout
- Role-based access control — **Customer** and **Admin** roles

### Menu & Cart
- Browse food categories and items (publicly accessible)
- Admin can add, update prices, and toggle item availability
- Cart system with real-time **price synchronisation** (detects price changes since item was added)

### Orders
- Atomic order placement using **PostgreSQL `SELECT FOR UPDATE`** locking
- Captures full **delivery address** per order (street, city, state, landmark, recipient name, phone, email, delivery date)
- Complete order **status lifecycle**: `Pending → Confirmed → Preparing → Out for Delivery → Completed`
- Customers can cancel pending orders; Admins can cancel at any stage
- Full status history log with actor and timestamp per transition

### Payments (Paystack)
- Supports **card, bank transfer, USSD, and mobile money** channels
- Payment initialisation returns `authorization_url` for Paystack checkout
- Webhook handler with **HMAC-SHA512 signature verification**
- Idempotent payment initialisation (no double-charging on retries)
- Payment status: `Pending → Success / Failed / Abandoned / Refunded`

### Async Notifications
- OTP emails sent **asynchronously** via Celery + Redis
- Order status update emails to customers
- Payment receipt emails on successful payment

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Framework | Django 4.2 + Django REST Framework 3.15 |
| Database | PostgreSQL 15 |
| Cache & Broker | Redis 7 |
| Task Queue | Celery 5 |
| Authentication | JWT via `djangorestframework-simplejwt` |
| Payments | Paystack API |
| Email | SMTP (Gmail or any provider) |
| Production Server | Gunicorn |

---

## 📁 Project Structure

```
chuks_kitchen/
├── apps/
│   ├── users/                  # Registration, OTP, JWT auth, referrals
│   │   ├── models.py           # User, OTP, UserProfile
│   │   ├── serializers.py      # Registration, OTP verify, login
│   │   ├── services.py         # OTP generation, throttling, verification
│   │   ├── views.py            # RegisterView, VerifyOTPView, LoginView
│   │   └── admin.py
│   ├── menu/                   # Categories, food items, cart
│   │   ├── models.py           # Category, FoodItem, Cart, CartItem
│   │   ├── serializers.py
│   │   ├── views.py            # CategoryViewSet, FoodItemViewSet, CartView
│   │   └── admin.py
│   ├── orders/                 # Order placement and lifecycle management
│   │   ├── models.py           # Order, OrderItem, DeliveryAddress, StatusHistory
│   │   ├── serializers.py      # PlaceOrder, OrderDetail, CancelOrder
│   │   ├── services.py         # Atomic order placement, status transitions
│   │   ├── views.py            # PlaceOrderView, AdminUpdateStatusView
│   │   └── admin.py
│   ├── payments/               # Paystack payment gateway
│   │   ├── models.py           # Payment model with full Paystack field mapping
│   │   ├── serializers.py
│   │   ├── services.py         # PaystackService — init, verify, webhook
│   │   ├── views.py            # InitiatePaymentView, WebhookView, CallbackView
│   │   └── admin.py
│   └── notifications/
│       └── tasks.py            # Celery async email tasks
├── config/
│   ├── settings.py             # All Django settings, reads from .env
│   ├── urls.py                 # Root URL configuration
│   ├── api_urls.py             # All API endpoint URL definitions
│   ├── permissions.py          # IsAdmin, IsCustomer, IsOrderOwnerOrAdmin
│   ├── pagination.py           # StandardResultsPagination (20 per page)
│   ├── exceptions.py           # Custom error response format + middleware
│   └── celery.py               # Celery application configuration
├── scripts/
│   └── seed_data.py            # Seed categories and food items
├── logs/                       # Application log files
├── media/                      # Uploaded images (food items, avatars)
├── staticfiles/                # Collected static files
├── manage.py
├── requirements.txt
├── .env.example                # Template for environment variables
└── .env                        # Your local secrets — never commit this
```

---

## 💻 System Requirements

| Software | Minimum Version | Check |
|----------|----------------|-------|
| Python | 3.11+ | `python3 --version` |
| PostgreSQL | 13+ | `psql --version` |
| Redis | 6+ | `redis-cli --version` |
| pip | 23+ | `pip --version` |
| Git | Any | `git --version` |

---

## ⚙️ Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/chuks-kitchen.git
cd chuks-kitchen
```

### 2. Create and Activate Virtual Environment

```bash
# Create
python3 -m venv venv

# Activate — macOS / Linux
source venv/bin/activate

# Activate — Windows (Command Prompt)
venv\Scripts\activate

# Activate — Windows (PowerShell)
venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the PostgreSQL Database

```bash
# Open PostgreSQL shell
sudo -u postgres psql

# Run these commands:
CREATE DATABASE chuks_kitchen;
CREATE USER chuks_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE chuks_kitchen TO chuks_user;
ALTER USER chuks_user CREATEDB;
\q
```

### 5. Set Up Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Open .env and fill in your values
nano .env   # or use any text editor
```

---

## 🔐 Environment Variables

Create a `.env` file in the project root. See `.env.example` for a template. Required variables:

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=chuks_kitchen
DB_USER=chuks_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379

# Email (Gmail — use an App Password, not your regular password)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your.email@gmail.com
EMAIL_HOST_PASSWORD=your_16_char_app_password
DEFAULT_FROM_EMAIL=Chuks Kitchen <noreply@chukskitchen.com>

# Paystack (get from dashboard.paystack.com > Settings > API Keys)
PAYSTACK_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
PAYSTACK_WEBHOOK_SECRET=your_webhook_secret

# URLs
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

> **⚠️ Important:** Add `.env` to your `.gitignore` immediately — never commit this file.
>
> Generate a secure `SECRET_KEY` with:
> ```bash
> python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

---

## 🚀 Running the Project

You need **four processes** running simultaneously. Open four terminal windows.

### Terminal 1 — Apply Migrations & Start Django Server

```bash
# Activate venv
source venv/bin/activate

# Run system check
python manage.py check

# Create and apply migrations
python manage.py makemigrations users menu orders payments
python manage.py migrate

# Create a superuser (admin account)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Seed initial menu data (optional but recommended)
python manage.py shell < scripts/seed_data.py

# Start the server
python manage.py runserver
```

Server is now live at: **http://127.0.0.1:8000**

### Terminal 2 — Celery Worker (Async Emails)

```bash
source venv/bin/activate
celery -A config worker --loglevel=info --concurrency=4
```

### Terminal 3 — Redis (if not running as a system service)

```bash
# macOS
brew services start redis

# Ubuntu / Debian
sudo systemctl start redis-server

# Verify
redis-cli ping  # Expected: PONG
```

### Terminal 4 — ngrok (for Paystack webhooks, local dev only)

```bash
# Install from https://ngrok.com
ngrok http 8000
# Copy the https://xxxx.ngrok.io URL
# Paste it into Paystack Dashboard > Settings > Webhooks:
# https://xxxx.ngrok.io/api/v1/payments/paystack/webhook/
```

---

## 🗺️ API Endpoints

Base URL: `http://127.0.0.1:8000/api/v1/`

### Authentication

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `auth/register/` | Register with email or phone | No |
| `POST` | `auth/verify-otp/` | Verify OTP → receive JWT tokens | No |
| `POST` | `auth/resend-otp/` | Resend OTP (60s cooldown) | No |
| `POST` | `auth/login/` | Login → JWT access + refresh tokens | No |
| `POST` | `auth/logout/` | Blacklist refresh token | Yes |
| `POST` | `auth/token/refresh/` | Get new access token | No |
| `GET` | `users/me/` | Get own profile | Yes |
| `PATCH` | `users/me/` | Update profile | Yes |

### Menu

| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| `GET` | `menu/categories/` | List active categories | Public |
| `POST` | `menu/categories/` | Create category | Admin |
| `GET` | `menu/items/` | List available food items | Public |
| `POST` | `menu/items/` | Add food item | Admin |
| `PATCH` | `menu/items/{id}/` | Update price / availability | Admin |

### Cart

| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| `GET` | `cart/` | View current cart | Customer |
| `DELETE` | `cart/` | Clear entire cart | Customer |
| `POST` | `cart/items/` | Add or update item in cart | Customer |
| `DELETE` | `cart/items/{id}/` | Remove item from cart | Customer |
| `PATCH` | `cart/items/{id}/quantity/` | Update item quantity | Customer |

### Orders

| Method | Endpoint | Description | Role |
|--------|----------|-------------|------|
| `POST` | `orders/place/` | Place order from cart | Customer |
| `GET` | `orders/` | My order history | Customer |
| `GET` | `orders/{id}/` | Order detail + delivery info | Customer / Admin |
| `POST` | `orders/{id}/cancel/` | Cancel a pending order | Customer |
| `GET` | `admin/orders/` | All orders (filterable) | Admin |
| `PATCH` | `admin/orders/{id}/status/` | Update order status | Admin |

### Payments

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `payments/initiate/` | Initialize Paystack payment | Yes |
| `GET` | `payments/verify/{reference}/` | Verify payment by reference | Yes |
| `GET` | `payments/history/` | Payment history | Yes |
| `POST` | `payments/paystack/webhook/` | Paystack webhook receiver | Signed |
| `GET` | `payments/paystack/callback/` | Post-payment redirect handler | No |

---

## 💳 Payment Integration

This project uses **Paystack** for all payment processing.

### Supported Channels

| Channel | Description |
|---------|-------------|
| `card` | Debit/Credit card (Visa, Mastercard, Verve) |
| `bank_transfer` | Direct bank transfer to virtual account |
| `ussd` | USSD code payment (`*737#`, `*770#`, etc.) |
| `mobile_money` | Mobile wallets (OPay, PalmPay, etc.) |

### Payment Flow

```
1. Customer places order  →  POST /api/v1/orders/place/
2. Response includes authorization_url  →  Open in browser/webview
3. Customer completes payment on Paystack
4. Paystack fires webhook  →  POST /api/v1/payments/paystack/webhook/
5. Webhook verified (HMAC-SHA512)  →  Order auto-confirmed
6. Receipt email sent to customer (Celery async)
```

### Test Card (Paystack sandbox)

```
Card Number : 4084 0840 8408 4081
Expiry      : Any future date
CVV         : Any 3 digits
PIN         : 0000
OTP         : 123456
```

---

## 🧪 Running Tests

```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test apps.users
python manage.py test apps.orders

# Run with verbose output
python manage.py test --verbosity=2
```

---

## 🌐 Deployment

### Production Checklist

- [ ] `DEBUG=False` in `.env`
- [ ] `SECRET_KEY` is a long random string
- [ ] `ALLOWED_HOSTS` set to your domain
- [ ] Paystack **live keys** (`sk_live_...`, `pk_live_...`) configured
- [ ] PostgreSQL hosted on a managed service (AWS RDS, Supabase, etc.)
- [ ] Redis hosted on a managed service (Redis Cloud, Upstash, etc.)
- [ ] Celery running as a background service (Supervisor or systemd)
- [ ] Static files served via Nginx or CDN
- [ ] HTTPS configured (SSL certificate)
- [ ] Webhook URL updated to production domain in Paystack dashboard

### Start Production Server

```bash
gunicorn config.wsgi:application --workers 4 --bind 0.0.0.0:8000
```

### Start Celery in Production

```bash
celery -A config worker --loglevel=info --concurrency=4 --detach
```

---

## 🔧 Useful Management Commands

```bash
# Check for configuration issues
python manage.py check --deploy

# Open Django shell
python manage.py shell

# Open database shell
python manage.py dbshell

# View all applied migrations
python manage.py showmigrations

# Reset a specific app's migrations (destructive — dev only)
python manage.py migrate users zero

# Monitor Celery tasks (requires flower)
pip install flower
celery -A config flower
# Open http://localhost:5555
```

---

## 📄 License

This project is licensed under the MIT License.

---

## 👤 Author

**Chuks Kitchen Team**

---

> Built with ❤️ using Django REST Framework