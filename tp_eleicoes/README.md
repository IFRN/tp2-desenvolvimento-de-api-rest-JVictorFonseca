# Sistema de Gerenciamento de Eleições

## Estratégia de Anonimato
Para atender aos requisitos de sigilo do voto, implementamos o **desacoplamento**:
* **RegistroVotacao**: Armazena quem compareceu (Eleitor + Eleicao).
* **Voto**: Armazena a escolha de forma anônima, sem qualquer vínculo (FK) com o eleitor.
* **Comprovante**: O sistema gera um token seguro e armazena apenas o seu hash SHA-256.

## Como Executar
1. Ative o ambiente: `source env/bin/activate`
2. Instale: `pip install -r requirements.txt`
3. Migre o banco: `python manage.py migrate`
4. Rode: `python manage.py runserver`