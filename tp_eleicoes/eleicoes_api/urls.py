from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from urna import views

router = DefaultRouter()
router.register(r'eleitores', views.EleitorViewSet)
router.register(r'eleicoes', views.EleicaoViewSet)
router.register(r'candidatos', views.CandidatoViewSet)
router.register(r'aptidoes', views.AptidaoEleitorViewSet)
router.register(r'registros-votacao', views.RegistroVotacaoViewSet)
router.register(r'votos', views.VotoViewSet)

schema_view = get_schema_view(
   openapi.Info(title="Eleições API", default_version='v1'),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('eleicoes_api/', include(router.urls)),
    
    # Rotas para verificação de voto e QR Code (Questão 04)
    path('eleicoes_api/verificar-comprovante/', views.verificar_comprovante),
    path('eleicoes_api/comprovantes/qr/', views.gerar_qr_code),
    
    # Swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0)),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0)),
]