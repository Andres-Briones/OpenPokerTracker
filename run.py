from app import create_app
import webbrowser
from threading import Timer
from math import sin, cos, acos

app = create_app()

@app.context_processor
def utility_processor():
    return dict(cos=cos, sin=sin, acos=acos)

def open_browser():
    """Open the default web browser at the Flask application's URL."""
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
   # Start the browser after a short delay to ensure the server is running
   # Timer(1, open_browser).start()
    app.run(debug=True)
    
