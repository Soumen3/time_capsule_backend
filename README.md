# Time Capsule Project

A modern web application for creating, sealing, and delivering digital time capsules to yourself or others in the future. Built with Django (backend) and React (frontend), supporting rich content, scheduled delivery, notifications, and secure authentication (including Google SSO and OTP-based flows).

---

## Features

- **User Registration & Login**
  - Email/Password registration with OTP email verification
  - Google SSO (Single Sign-On) integration
  - Secure password reset via OTP
  - JWT and DRF Token authentication

- **Time Capsule Creation**
  - Multi-step capsule creation wizard
  - Add text, images, videos, audio, and documents
  - Schedule delivery date and time
  - Assign recipients by email

- **Capsule Delivery & Viewing**
  - Capsules are delivered to recipients on the scheduled date
  - Recipients receive a secure link via email
  - Public and private capsule viewing modes

- **Dashboard & Management**
  - Dashboard with capsule status: Sealed, Delivered, Opened, Draft
  - Capsule editing, deletion, and detailed view
  - User profile management

- **Notifications**
  - In-app notifications for delivery, opening, and system events

- **Dark/Light Theme**
  - Theme switcher with persistent preference (localStorage)
  - Fully responsive and accessible UI

---

## Tech Stack

- **Frontend:** React, Tailwind CSS, Vite, Axios
- **Backend:** Django, Django REST Framework, SimpleJWT, Celery, PostgreSQL
- **Storage:** AWS S3 (for media files)
- **Email:** SMTP (Gmail or custom)
- **SSO:** Google Identity Services (`@react-oauth/google`)
- **Other:** Docker-ready, Celery for scheduled tasks, CORS configured

---

## Getting Started

### Prerequisites

- Node.js (v18+ recommended)
- Python 3.10+
- PostgreSQL
- Redis (for Celery)
- AWS S3 bucket (for media)
- Google Cloud OAuth Client ID

### 1. Clone the Repository

```bash
git clone https://github.com/Soumen3/time_capsule.git
cd time_capsule
```

### 2. Backend Setup

#### a. Environment Variables

Create a `.env` file in the backend root (`time_capsule_backend/`) with:

```
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

EMAIL_USER=your.email@gmail.com
EMAIL_PASSWORD=your_app_password

IAM_USER_ACCESS_KEY=your_aws_access_key
IAM_USER_SECRET_ACCESS_KEY=your_aws_secret_key
S3BUCKET_NAME=your_s3_bucket
REGION=your_s3_region

VITE_GOOGLE_CLIENT_ID=your_google_client_id
```

#### b. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### c. Run Migrations

```bash
python manage.py migrate
```

#### d. Create Superuser

```bash
python manage.py createsuperuser
```

#### e. Start Celery Worker (in a new terminal)

```bash
celery -A time_capsule_backend worker -l info
celery -A time_capsule_backend beat -l info
```

#### f. Run the Backend Server

```bash
python manage.py runserver
```

---

### 3. Frontend Setup

#### a. Environment Variables

Create a `.env` file in the frontend root (`time-capsule-frontend/`) with:

```
VITE_API_BASE_URL=http://localhost:8000/api/
VITE_GOOGLE_CLIENT_ID=your_google_client_id
```

#### b. Install Dependencies

```bash
cd time-capsule-frontend
npm install
```

#### c. Start the Frontend

```bash
npm run dev
```

---

## Usage

- Visit `http://localhost:5173` in your browser.
- Register a new account (OTP verification required) or use Google SSO.
- Create and manage time capsules from your dashboard.
- Recipients will receive email notifications and secure links to view capsules.

---

## Project Structure

```
time-capsule-project/
├── time_capsule_backend/      # Django backend
│   ├── accounts/              # User, auth, SSO, OTP, notifications
│   ├── capsules/              # Capsule models, delivery, content
│   ├── time_capsule_backend/  # Django project settings
│   └── ...
├── time-capsule-frontend/     # React frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── context/
│   │   ├── services/
│   │   └── ...
│   └── ...
└── README.md
```

---

## Customization & Tips

- **Theme:** Use the theme toggle button (usually in the navbar) to switch between light and dark mode.
- **Google SSO:** Make sure your Google OAuth Client ID is set in both frontend and backend `.env` files.
- **Email:** For production, use a secure email provider and app password.
- **Media:** All uploaded files are stored in AWS S3.
- **Celery:** Required for scheduled delivery of capsules.

---

## Security Notes

- All sensitive data (tokens, passwords, keys) should be stored in environment variables.
- HTTPS is recommended for production.
- CORS is configured for local development; update allowed origins for production.

---

## License

MIT License

---

## Credits

- [Django](https://www.djangoproject.com/)
- [React](https://react.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Google Identity Services](https://developers.google.com/identity)
- [AWS S3](https://aws.amazon.com/s3/)
- [Celery](https://docs.celeryq.dev/)

---

## Contact

For questions or support, open an issue or contact the maintainer at [soumensamanta112233@gmail.com](mailto:soumensamanta112233@gmail.com).

