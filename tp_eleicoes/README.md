# Sistema de Gerenciamento de Eleições

## Estratégia de Anonimato
[cite_start]Para atender aos requisitos de sigilo do voto[cite: 238, 247], implementamos o **desacoplamento**:
* [cite_start]**RegistroVotacao**: Armazena quem compareceu (Eleitor + Eleicao)[cite: 264, 311].
* [cite_start]**Voto**: Armazena a escolha de forma anônima, sem qualquer vínculo (FK) com o eleitor[cite: 240, 316].
* [cite_start]**Comprovante**: O sistema gera um token seguro e armazena apenas o seu hash SHA-256[cite: 250, 323].

## Como Executar
1. Ative o ambiente: `source env/bin/activate`
2. Instale: `pip install -r requirements.txt`
3. Migre o banco: `python manage.py migrate`
4. Rode: `python manage.py runserver`