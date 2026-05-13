import secrets
import hashlib
import qrcode
from io import BytesIO
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count
from django.db import IntegrityError
from .models import *
from .serializers import *

class EleitorViewSet(viewsets.ModelViewSet):
    queryset = Eleitor.objects.all()
    serializer_class = EleitorSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['ativo']
    search_fields = ['nome', 'email', 'cpf']

class CandidatoViewSet(viewsets.ModelViewSet):
    queryset = Candidato.objects.select_related('eleicao').all()
    serializer_class = CandidatoSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['eleicao']
    search_fields = ['nome', 'nome_urna', 'partido_ou_chapa']

class AptidaoEleitorViewSet(viewsets.ModelViewSet):
    queryset = AptidaoEleitor.objects.select_related('eleitor', 'eleicao').all()
    serializer_class = AptidaoEleitorSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['eleitor', 'eleicao']

class RegistroVotacaoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RegistroVotacao.objects.all()
    serializer_class = RegistroVotacaoSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['eleicao']
    ordering_fields = ['data_hora']
    ordering = ['-data_hora']

class VotoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Voto.objects.all()
    serializer_class = VotoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['eleicao']

class EleicaoViewSet(viewsets.ModelViewSet):
    queryset = Eleicao.objects.all()
    serializer_class = EleicaoSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'tipo', 'criada_por']
    search_fields = ['titulo']
    ordering_fields = ['data_inicio']

    # --- Q05: GESTÃO DO CICLO DA ELEIÇÃO ---
    @action(detail=True, methods=['post'])
    def abrir(self, request, pk=None):
        eleicao = self.get_object()
        if eleicao.status != 'rascunho':
            return Response({'erro': 'Apenas rascunhos podem ser abertos'}, status=400)
        if eleicao.candidatos.count() < 2:
            return Response({'erro': 'Mínimo de 2 candidatos necessários'}, status=400)
        if eleicao.aptos.count() < 1:
            return Response({'erro': 'Mínimo de 1 eleitor apto necessário'}, status=400)
        
        eleicao.status = 'aberta'
        eleicao.save()
        return Response(EleicaoSerializer(eleicao).data)

    @action(detail=True, methods=['post'])
    def encerrar(self, request, pk=None):
        eleicao = self.get_object()
        if eleicao.status != 'aberta':
            return Response({'erro': 'Apenas eleições abertas podem ser encerradas'}, status=400)
        eleicao.status = 'encerrada'
        eleicao.save()
        return Response(EleicaoSerializer(eleicao).data)

    @action(detail=True, methods=['post'], url_path='cadastrar-aptos')
    def cadastrar_aptos(self, request, pk=None):
        eleicao = self.get_object()
        if eleicao.status != 'rascunho':
            return Response({'erro': 'Eleição não está em rascunho'}, status=400)
        
        ids = request.data.get('eleitores_ids', [])
        criados = 0
        for e_id in ids:
            obj, created = AptidaoEleitor.objects.get_or_create(eleicao=eleicao, eleitor_id=e_id)
            if created: criados += 1
            
        return Response({'total_cadastrados': criados})

    # --- Q04: VOTAÇÃO (SIGILO E COMPROVANTE) ---
    @action(detail=True, methods=['post'])
    def votar(self, request, pk=None):
        data = request.data.copy()
        data['eleicao_id'] = pk
        serializer = VotacaoInputSerializer(data=data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        vd = serializer.validated_data
        
        try:
            # 1. Registra o comparecimento
            RegistroVotacao.objects.create(eleitor_id=vd['eleitor_id'], eleicao_id=vd['eleicao_id'])
        except IntegrityError:
            return Response({'mensagem': 'Eleitor já votou nesta eleição'}, status=status.HTTP_409_CONFLICT)

        # 2. Gera token e Hash (Garantia do Sigilo)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # 3. Salva o voto anonimamente
        voto = Voto.objects.create(
            eleicao_id=vd['eleicao_id'],
            candidato_id=vd.get('candidato_id'),
            em_branco=vd.get('em_branco', False),
            comprovante_hash=token_hash
        )

        candidato_nome = f"{voto.candidato.nome_urna} (#{voto.candidato.numero})" if voto.candidato else "BRANCO"

        return Response({
            "mensagem": "Voto registrado com sucesso. Guarde o seu comprovante.",
            "comprovante": {
                "token": token,
                "eleicao": voto.eleicao.titulo,
                "candidato": candidato_nome,
                "data_hora": voto.data_hora,
                "qr_code_url": f"/eleicoes_api/comprovantes/qr/?token={token}"
            }
        }, status=status.HTTP_201_CREATED)

    # --- Q05: RELATÓRIOS E APURAÇÃO ---
    @action(detail=True, methods=['get'])
    def apuracao(self, request, pk=None):
        eleicao = self.get_object()
        if eleicao.status not in ['encerrada', 'apurada']:
            return Response({'erro': 'Eleição ainda não encerrada'}, status=status.HTTP_403_FORBIDDEN)

        total_aptos = eleicao.aptos.count()
        total_votantes = eleicao.registros_votacao.count()
        votos_brancos = eleicao.votos.filter(em_branco=True).count()
        votos_validos = eleicao.votos.filter(em_branco=False).count()

        resultado = []
        candidatos = eleicao.candidatos.annotate(votos_recebidos=Count('votos')).order_by('-votos_recebidos')
        
        vencedores = []
        max_votos = -1
        
        for i, c in enumerate(candidatos):
            pct = (c.votos_recebidos / votos_validos * 100) if votos_validos > 0 else 0
            resultado.append({
                "posicao": i + 1, "candidato": c.nome_urna, "numero": c.numero,
                "votos": c.votos_recebidos, "percentual": round(pct, 2)
            })
            if c.votos_recebidos > max_votos:
                max_votos = c.votos_recebidos
                vencedores = [c.nome_urna]
            elif c.votos_recebidos == max_votos and max_votos > 0:
                vencedores.append(c.nome_urna)

        if eleicao.status == 'encerrada':
            eleicao.status = 'apurada'
            eleicao.save()

        return Response({
            "eleicao": eleicao.titulo, "total_aptos": total_aptos,
            "total_votantes": total_votantes, "total_abstencoes": total_aptos - total_votantes,
            "votos_validos": votos_validos, "votos_brancos": votos_brancos,
            "comparecimento_pct": round((total_votantes / total_aptos * 100), 2) if total_aptos > 0 else 0,
            "resultado": resultado, "vencedores": vencedores, "houve_empate": len(vencedores) > 1
        })

    @action(detail=True, methods=['get'])
    def votantes(self, request, pk=None):
        eleicao = self.get_object()
        compareceu = request.query_params.get('compareceu')
        
        if compareceu == 'false':
            aptos_ids = eleicao.aptos.values_list('eleitor_id', flat=True)
            votantes_ids = eleicao.registros_votacao.values_list('eleitor_id', flat=True)
            abstencoes = Eleitor.objects.filter(id__in=aptos_ids).exclude(id__in=votantes_ids)
            data = [{"nome": e.nome, "cpf": f"***.{e.cpf[4:7]}.***-**"} for e in abstencoes]
        else:
            registros = eleicao.registros_votacao.select_related('eleitor')
            data = [{"nome": r.eleitor.nome, "cpf": f"***.{r.eleitor.cpf[4:7]}.***-**", "data_hora": r.data_hora} for r in registros]
            
        return Response(data)

# --- VIEWS PÚBLICAS PARA QR CODE ---
@api_view(['GET'])
def verificar_comprovante(request):
    token = request.GET.get('token', '')
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    try:
        voto = Voto.objects.get(comprovante_hash=token_hash)
        candidato_str = voto.candidato.nome_urna if voto.candidato else 'BRANCO'
        return Response({
            "eleicao": voto.eleicao.titulo, "candidato": candidato_str,
            "data_hora": voto.data_hora, "valido": True
        })
    except Voto.DoesNotExist:
        return Response({"valido": False, "mensagem": "Comprovante inválido"}, status=404)

@api_view(['GET'])
def gerar_qr_code(request):
    token = request.GET.get('token', '')
    url = f"http://{request.get_host()}/eleicoes_api/verificar-comprovante/?token={token}"
    img = qrcode.make(url)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")