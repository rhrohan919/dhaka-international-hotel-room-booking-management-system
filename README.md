# Hotel Room Booking Management System

A Django-based hotel reservation application for room search, booking, management, and reporting.

## Project overview

This project is designed for a hotel business that needs:

- customer registration and authentication
- room browsing and filtering
- booking availability checks with overlapping-date protection
- secure booking creation and status updates
- customer dashboards and admin management
- deployment-ready configuration for local and production environments

## Phase 1 completed

This phase establishes the core project foundation:

- Django project configuration for safe environment-based settings
- SQLite by default with optional PostgreSQL configuration
- static and media folder setup
- base template and front-end shell
- login/register flow structure
- deployment-ready environment examples and dependency file

## Proposed architecture

```text
Clients (Browser / API / Admin)
        |
        v
Django Views + Templates
        |
        v
Services / business logic
        |
        v
Models + ORM
        |
        v
SQLite for local dev / PostgreSQL for production
```

## Database relationship diagram

```text
User
  1 ── 1 CustomerProfile
  1 ── many Booking
  1 ── many Payment
  1 ── many Review
  1 ── many ContactMessage

RoomType
  1 ── many Room

Room
  1 ── many RoomImage
  1 ── many Booking

Booking
  many ── 1 Room
  many ── 1 User
  1 ── many Payment

Payment
  many ── 1 Booking
```

## Features in this repo

- customer registration and login
- room list and details pages
- room availability checks
- booking creation flow
- booking status management
- responsive layout with a premium hotel design

## Setup

### 1. Create a virtual environment

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create environment file

Copy the example environment file:

```bash
copy .env.example .env
```

Then update the values in `.env` for your local setup.

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Create an admin user

```bash
python manage.py createsuperuser
```

### 6. Run the development server

```bash
python manage.py runserver
```

### 7. Load demo data

```bash
python manage.py populate_rooms
```

## Environment variables

The project reads the following values from environment variables:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DATABASE_URL`
- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`

## Deployment notes

The settings file supports both SQLite and PostgreSQL. For PostgreSQL, configure `DATABASE_URL` in the environment and deploy with `DEBUG=False` and a safe `ALLOWED_HOSTS` value.

## Next phases

- Phase 2: advanced room management and room details
- Phase 3: robust booking engine and price validation
- Phase 4: customer dashboard and invoice flow
- Phase 5: admin analytics and room management
- Phase 6: payment, email, and reviews
- Phase 7: testing, security review, and deployment hardening

| Check-In               | POST   | `/api/bookings/{id}/checkin/`       |
| Check-Out              | POST   | `/api/bookings/{id}/checkout/`      |
| Cancel Booking         | POST   | `/api/bookings/{id}/cancel/`        |

---

## 🔐 Authentication

* **Web UI** → Django session authentication
* **API** → Token authentication

**API Header Example**

```
Authorization: Token <your_token>
```

---

## 🚫 Double Booking Prevention (Key Logic)

A room **cannot be booked** if:

* There is an existing booking with status:

  ```
  pending, confirmed, checked_in
  ```
* AND the time overlaps:

  ```
  existing.start_time < new.end_time
  AND
  existing.end_time > new.start_time
  ```

This logic is implemented in:

```
bookings/services.py → BookingService.check_room_availability()
```

Used by:

* Booking API
* Template booking flow

✔ One rule, enforced everywhere

---

## 🧪 Example Workflow

1. Admin runs `populate_rooms`
2. User A books Room 202 (10:00–14:00)
3. User B tries booking Room 202 (11:00–13:00)

   * ❌ Blocked
4. User A checks out
5. User B books same room

   * ✅ Allowed

---

