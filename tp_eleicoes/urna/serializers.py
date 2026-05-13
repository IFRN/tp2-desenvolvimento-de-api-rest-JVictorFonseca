import re
from rest_framework import serializers
from django.utils.timezone import now
from .models import *

class EleitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Eleitor
        fields = '__all__'

    def validate_cpf(self, value):
        if not re.match(r'^\d{3}\.\d{3}\.\d{3}-\d{2}$', value):
            raise serializers.ValidationError("Formato inválido. Use 000.000.000-00")
        return value

class EleicaoSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_candidatos = serializers.SerializerMethodField()
    total_aptos = serializers.SerializerMethodField()

    class Meta:
        model = Eleicao
        fields = '__all__'

    def get_total_candidatos(self, obj):
        return obj.candidatos.count()

    def get_total_aptos(self, obj):
        return obj.aptos.count()

class CandidatoSerializer(serializers.ModelSerializer):
    eleicao_titulo = serializers.CharField(source='eleicao.titulo', read_only=True)

    class Meta:
        model = Candidato
        fields = '__all__'

    def validate_numero(self, value):
        if value == 0:
            raise serializers.ValidationError("O número zero é reservado para votos em branco.")
        return value

class AptidaoEleitorSerializer(serializers.ModelSerializer):
    eleitor_nome = serializers.CharField(source='eleitor.nome', read_only=True)
    eleicao_titulo = serializers.CharField(source='eleicao.titulo', read_only=True)

    class Meta:
        model = AptidaoEleitor
        fields = '__all__'

class RegistroVotacaoSerializer(serializers.ModelSerializer):
    eleitor_nome = serializers.CharField(source='eleitor.nome', read_only=True)
    eleicao_titulo = serializers.CharField(source='eleicao.titulo', read_only=True)

    class Meta:
        model = RegistroVotacao
        fields = '__all__'
        read_only_fields = ['eleitor', 'eleicao', 'data_hora']

class VotoSerializer(serializers.ModelSerializer):
    candidato_nome_urna = serializers.CharField(source='candidato.nome_urna', read_only=True, allow_null=True)
    em_branco_display = serializers.SerializerMethodField()

    class Meta:
        model = Voto
        # Excluímos o comprovante_hash para NUNCA ser exposto nas respostas da API
        exclude = ['comprovante_hash']

    def get_em_branco_display(self, obj):
        return 'BRANCO' if obj.em_branco else None

class VotacaoInputSerializer(serializers.Serializer):
    eleitor_id = serializers.IntegerField()
    eleicao_id = serializers.IntegerField()
    candidato_id = serializers.IntegerField(required=False, allow_null=True)
    em_branco = serializers.BooleanField(default=False)

    def validate(self, data):
        try:
            eleicao = Eleicao.objects.get(id=data['eleicao_id'])
        except Eleicao.DoesNotExist:
            raise serializers.ValidationError("Eleição não encontrada.")

        if eleicao.status != 'aberta':
            raise serializers.ValidationError("Eleição não está aberta para votação.")
        if not (eleicao.data_inicio <= now() <= eleicao.data_fim):
            raise serializers.ValidationError("Fora do período de votação.")
        if not AptidaoEleitor.objects.filter(eleicao=eleicao, eleitor_id=data['eleitor_id']).exists():
            raise serializers.ValidationError("Eleitor não está apto para esta eleição.")
        if RegistroVotacao.objects.filter(eleicao=eleicao, eleitor_id=data['eleitor_id']).exists():
            raise serializers.ValidationError("Eleitor já votou nesta eleição.")

        candidato_id = data.get('candidato_id')
        em_branco = data.get('em_branco', False)

        if (candidato_id and em_branco) or (not candidato_id and not em_branco):
            raise serializers.ValidationError("Informe exatamente um candidato_id OU em_branco=True.")

        if candidato_id and not Candidato.objects.filter(id=candidato_id, eleicao=eleicao).exists():
            raise serializers.ValidationError("Candidato não pertence a esta eleição.")

        return data