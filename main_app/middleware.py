from django.utils.deprecation import MiddlewareMixin
from django.urls import reverse
from django.shortcuts import redirect


class LoginCheckMiddleWare(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        modulename = view_func.__module__
        user = request.user  # Who is the current user?
        if user.is_authenticated:
            if user.role == 'HOD':  # HOD/Admin
                if modulename == 'main_app.student_views':
                    return redirect(reverse('admin_home'))
            elif user.role in ['FACULTY', 'GUEST']:  # Faculty or Guest Faculty
                if modulename == 'main_app.student_views' or modulename == 'main_app.hod_views':
                    return redirect(reverse('staff_home'))
            elif user.role == 'STUDENT':  # Student
                if modulename == 'main_app.hod_views' or modulename == 'main_app.staff_views':
                    return redirect(reverse('student_home'))
            elif user.role == 'STAFF':  # Non-teaching staff (lab assistants)
                # Non-teaching staff can only access limited areas
                if modulename == 'main_app.hod_views' or modulename == 'main_app.student_views':
                    return redirect(reverse('staff_home'))
            else:  # None of the aforementioned? Please take the user to login page
                return redirect(reverse('login_page'))
        else:
            if request.path == reverse('login_page') or modulename == 'django.contrib.auth.views' or request.path == reverse('user_login'):
                # If the path is login or has anything to do with authentication, pass
                pass
            else:
                return redirect(reverse('login_page'))
