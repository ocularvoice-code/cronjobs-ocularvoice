from main import app
from mangum import Mangum

# Convertir FastAPI a handler de Lambda
handler = Mangum(app)