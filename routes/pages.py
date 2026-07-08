"""
ChefMate-Agent — Page Routes

Serves HTML pages:
  GET /          — Home page
  GET /chat      — AI Chat page
  GET /features  — Features (redirect to home#features)
"""

from flask import Blueprint, render_template, redirect, url_for

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def home():
    return render_template("index.html")


@pages_bp.route("/chat")
def chat():
    return render_template("chat.html")


@pages_bp.route("/features")
def features():
    return redirect(url_for("pages.home") + "#features")
