"""
Anna University CSE Department ERP System
Main Views - Authentication, Common Functions
"""

import json
import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from main_app.utils.web_scrapper import fetch_acoe_updates
from main_app.utils.cir_scrapper import fetch_cir_news, fetch_cir_ticker_announcements

from .EmailBackend import EmailBackend
from .models import (
    Account_User, Attendance, Course_Assignment, AcademicYear, Semester,
    Announcement, Notification
)


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

def login_page(request):
    """Login page - redirects authenticated users to their dashboard"""
    if request.user.is_authenticated:
        return redirect_to_dashboard(request.user)
    return render(request, 'main_app/login.html')


def redirect_to_dashboard(user):
    """Redirect user to appropriate dashboard based on role"""
    role_redirects = {
        'HOD': 'admin_home',
        'FACULTY': 'staff_home',
        'GUEST': 'staff_home',
        'STAFF': 'staff_home',
        'STUDENT': 'student_home',
    }
    return redirect(reverse(role_redirects.get(user.role, 'student_home')))


def doLogin(request, **kwargs):
    """Handle login form submission"""
    if request.method != 'POST':
        return HttpResponse("<h4>Denied</h4>")
    
    # Google reCAPTCHA verification
    captcha_token = request.POST.get('g-recaptcha-response')
    captcha_url = "https://www.google.com/recaptcha/api/siteverify"
    captcha_key = "6LfTGD4qAAAAALtlli02bIM2MGi_V0cUYrmzGEGd"
    data = {
        'secret': captcha_key,
        'response': captcha_token
    }
    
    try:
        captcha_server = requests.post(url=captcha_url, data=data)
        response = json.loads(captcha_server.text)
        if not response['success']:
            messages.error(request, 'Invalid Captcha. Try Again')
            return redirect('/')
    except:
        messages.error(request, 'Captcha could not be verified. Try Again')
        return redirect('/')
    
    # Authenticate user
    user = EmailBackend.authenticate(
        request, 
        username=request.POST.get('email'), 
        password=request.POST.get('password')
    )
    
    if user is not None:
        # Check if user is active
        if not user.is_active:
            messages.error(request, "Your account has been deactivated. Please contact administrator.")
            return redirect("/")
        
        # Check for guest faculty contract expiry
        if user.role == 'GUEST':
            try:
                if user.faculty_profile.is_contract_expired:
                    messages.error(request, "Your contract has expired. Please contact HOD.")
                    return redirect("/")
            except:
                pass
        
        login(request, user)
        messages.success(request, f"Welcome, {user.full_name}!")
        return redirect_to_dashboard(user)
    else:
        messages.error(request, "Invalid email or password")
        return redirect("/")


def logout_user(request):
    """Handle user logout"""
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "You have been logged out successfully.")
    return redirect("/")


# =============================================================================
# COMMON API VIEWS
# =============================================================================

@csrf_exempt
def get_attendance(request):
    """API to get attendance data for a course assignment"""
    assignment_id = request.POST.get('assignment')
    
    try:
        assignment = get_object_or_404(Course_Assignment, id=assignment_id)
        attendance = Attendance.objects.filter(assignment=assignment)
        attendance_list = []
        
        for attd in attendance:
            data = {
                "id": attd.id,
                "attendance_date": str(attd.date),
                "period": attd.period,
                "status": attd.status,
                "student": attd.student.register_no
            }
            attendance_list.append(data)
        
        return JsonResponse(json.dumps(attendance_list), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def get_notifications(request):
    """API to get user notifications"""
    notifications = Notification.objects.filter(
        recipient=request.user, 
        is_read=False
    ).order_by('-created_at')[:10]
    
    notification_list = [{
        'id': str(n.id),
        'title': n.title,
        'message': n.message[:100],
        'type': n.notification_type,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
        'link': n.link
    } for n in notifications]
    
    return JsonResponse({'notifications': notification_list, 'count': len(notification_list)})


@login_required
@csrf_exempt
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)


# =============================================================================
# FIREBASE MESSAGING
# =============================================================================

def showFirebaseJS(request):
    """Serve Firebase service worker JavaScript"""
    data = """
    // Give the service worker access to Firebase Messaging.
// Note that you can only use Firebase Messaging here, other Firebase libraries
// are not available in the service worker.
importScripts('https://www.gstatic.com/firebasejs/7.22.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/7.22.1/firebase-messaging.js');

// Initialize the Firebase app in the service worker by passing in
// your app's Firebase config object.
// https://firebase.google.com/docs/web/setup#config-object
firebase.initializeApp({
    apiKey: "AIzaSyBarDWWHTfTMSrtc5Lj3Cdw5dEvjAkFwtM",
    authDomain: "sms-with-django.firebaseapp.com",
    databaseURL: "https://sms-with-django.firebaseio.com",
    projectId: "sms-with-django",
    storageBucket: "sms-with-django.appspot.com",
    messagingSenderId: "945324593139",
    appId: "1:945324593139:web:03fa99a8854bbd38420c86",
    measurementId: "G-2F2RXTL9GT"
});

// Retrieve an instance of Firebase Messaging so that it can handle background
// messages.
const messaging = firebase.messaging();
messaging.setBackgroundMessageHandler(function (payload) {
    const notification = JSON.parse(payload);
    const notificationOption = {
        body: notification.body,
        icon: notification.icon
    }
    return self.registration.showNotification(payload.notification.title, notificationOption);
});
    """
    return HttpResponse(data, content_type='application/javascript')


# =============================================================================
# ANNOUNCEMENTS & NEWS
# =============================================================================

def announcements(request):
    """Display Anna University announcements and news"""
    # Fetch external announcements with error handling
    cir_ticker = []
    cir_news = []
    acoe_updates = []
    
    try:
        cir_ticker = fetch_cir_ticker_announcements(limit=10)
    except Exception:
        pass
    
    try:
        cir_news = fetch_cir_news(limit=6)
    except Exception:
        pass
    
    try:
        acoe_updates = fetch_acoe_updates()
    except Exception:
        pass
    
    # Get department announcements
    dept_announcements = Announcement.objects.filter(is_active=True).order_by('-is_pinned', '-created_at')[:10]

    context = {
        "page_title": "Announcements",
        "cir_ticker": cir_ticker,
        "cir_news": cir_news,
        "acoe_updates": acoe_updates,
        "dept_announcements": dept_announcements,
    }
    return render(request, "./announcements/announcements.html", context)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_current_academic_context():
    """Get current academic year and semester"""
    academic_year = AcademicYear.objects.filter(is_current=True).first()
    semester = Semester.objects.filter(is_current=True).first()
    return {
        'current_academic_year': academic_year,
        'current_semester': semester
    }


def send_notification(recipient, title, message, notification_type='INFO', sender=None, link=None):
    """Helper function to create and send notifications"""
    return Notification.objects.create(
        recipient=recipient,
        sender=sender,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link
    )