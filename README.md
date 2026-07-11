# AirGuard Community Dashboard

This is a Django development project for the AirGuard Community Dashboard.

These steps assume you are new to Git, Python packages, and Django. Follow them in order.

## 1. Install Git

Git downloads the project from GitHub.

1. Go to https://git-scm.com/downloads.
2. Download Git for your computer.
3. Run the installer.
4. On Windows, you can accept the default installer choices.

To check that Git installed correctly, open Command Prompt and run:

```cmd
git --version
```

## 2. Install Python

Python runs Django.

1. Go to https://www.python.org/downloads/.
2. Download Python 3.
3. Run the installer.
4. On Windows, check the box that says **Add python.exe to PATH** before installing.

To check that Python installed correctly, open Command Prompt and run:

```cmd
python --version
pip --version
```

## 3. Download The Project

Choose one option.

### Option A: Download With Git

Open Command Prompt, move to the folder where you keep projects, then clone the repository:

```cmd
cd %USERPROFILE%\Documents
git clone https://github.com/myk-sev/AirGuard-Community-Dashboard-2026.git
cd AirGuard-Community-Dashboard-2026
```

### Option B: Download A ZIP File

1. Open the project page on GitHub.
2. Click **Code**.
3. Click **Download ZIP**.
4. Unzip the downloaded file.
5. Open Command Prompt in the unzipped project folder.

## 4. Create The Virtual Environment

A virtual environment keeps this project's Python packages separate from the rest of your computer.

From the project folder, run:

```cmd
python -m venv .venv
```

Turn it on:

```cmd
.venv\Scripts\activate.bat
```

When it is active, your command line will start with `(.venv)`.

## 5. Install The Python Packages

With the virtual environment active, run:

```cmd
python -m pip install -r requirements.txt
```

This installs Django and the helper library that reads the local `.env` file.

## 6. Create The Development Settings File

Create a file named `.env` in the project folder.

Put this line in it:

```text
DJANGO_SECRET_KEY=ask-a-team-member-for-the-development-key
```

The `.env` file is private to your computer and should not be committed to GitHub.

## 7. Set Up The Database

With the virtual environment active, run:

```cmd
python manage.py migrate
```

Optional: load demo data for local development:

```cmd
python manage.py seed_demo
```

## 8. Start The Development Server

With the virtual environment active, run:

```cmd
python manage.py runserver
```

Open this address in your browser:

```text
http://127.0.0.1:8000/
```

To stop the server, press `Ctrl+C` in Command Prompt.

## Common Commands

Turn on the virtual environment:

```cmd
.venv\Scripts\activate.bat
```

Install packages after `requirements.txt` changes:

```cmd
python -m pip install -r requirements.txt
```

Run database updates:

```cmd
python manage.py migrate
```

Start Django:

```cmd
python manage.py runserver
```
