class JsonCharsetMiddleware:
   
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.has_header('Content-Type'):
            content_type = response['Content-Type']
            if 'application/json' in content_type and 'charset' not in content_type:
                response['Content-Type'] = f"{content_type}; charset=utf-8"
        return response
