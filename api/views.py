from django.http import JsonResponse

def getRoutes(request):
    routes = [
        {'GET': '/api/projects'},
        {'GET': '/api/projects/id'},
        {'POST': '/api/projects/id/like'},

        {'POST': '/api/user/token'},
        {'POST': '/api/user/token/refresh'},
    ]
    return JsonResponse(routes, safe=False)