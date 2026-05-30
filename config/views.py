from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render


@login_required(login_url='account_login')
def home(request):
    return render(request, 'home.html')


def signup_disabled(request):
    raise Http404("Sign up is disabled")
