"""Resposta ao backend. O serviço não persiste dados nem aprova a FDS."""
from typing import Literal
from pydantic import Field, model_validator
from .entrada import Documento
from .evidencia import Evidencia, NumeroSecao, SchemaBase, Texto
from .composto import Composto
from .primeiro_socorro import PrimeiroSocorro, OrientacaoGeral
from .incompatibilidade import Incompatibilidade

class Pendencia(SchemaBase):
    secao: NumeroSecao
    campo: Texto
    motivo: Literal['secao_nao_localizada', 'informacao_ausente', 'documento_nao_especifica', 'termo_ambiguo', 'dados_contraditorios', 'evidencia_invalida']
    descricao: Texto
    evidencias: list[Evidencia]

class ComposicaoExtraida(SchemaBase):
    encontrada: bool
    compostos: list[Composto]

class PrimeirosSocorrosExtraidos(SchemaBase):
    encontrada: bool
    primeiros_socorros: list[PrimeiroSocorro]
    orientacoes_gerais: list[OrientacaoGeral]
    notas_ao_medico: list[OrientacaoGeral]

    @model_validator(mode='after')
    def validar_rotas(self):
        rotas = [item.rota_exposicao for item in self.primeiros_socorros]
        if len(rotas) != len(set(rotas)):
            raise ValueError('Agrupe as informações de cada rota em um único registro.')
        return self

class IncompatibilidadesExtraidas(SchemaBase):
    encontrada: bool
    situacao: Literal['identificadas', 'ausencia_declarada', 'nao_especificadas', 'secao_nao_localizada']
    incompatibilidades: list[Incompatibilidade]
    evidencias: list[Evidencia]

    @model_validator(mode='after')
    def validar_situacao(self):
        if self.encontrada != (self.situacao != 'secao_nao_localizada'):
            raise ValueError('Situação deve corresponder à localização da seção 10.')
        if bool(self.incompatibilidades) != (self.situacao == 'identificadas'):
            raise ValueError('Somente a situação identificadas deve conter incompatibilidades.')
        if self.situacao == 'ausencia_declarada' and not self.evidencias:
            raise ValueError('Ausência declarada exige evidência explícita no documento.')
        return self

class SecoesSaida(SchemaBase):
    composicao: ComposicaoExtraida = Field(alias='03')
    primeiros_socorros: PrimeirosSocorrosExtraidos = Field(alias='04')
    incompatibilidades: IncompatibilidadesExtraidas = Field(alias='10')

class ExtracaoSaida(SchemaBase):
    documento: Documento
    status: Literal['processado', 'processado_com_pendencias']
    mensagem: Texto | None
    secoes: SecoesSaida
    pendencias: list[Pendencia]
    requer_confirmacao: Literal[True] = Field(description='A aprovação pela empresa é necessária mesmo sem pendências.')

    @model_validator(mode='after')
    def validar_status(self):
        if bool(self.pendencias) != (self.status == 'processado_com_pendencias'):
            raise ValueError('Status deve refletir a existência de pendências.')
        if self.pendencias and not self.mensagem:
            raise ValueError('Resposta com pendências exige mensagem para revisão.')
        for numero, secao, itens in [
            ('03', self.secoes.composicao, self.secoes.composicao.compostos),
            ('04', self.secoes.primeiros_socorros, self.secoes.primeiros_socorros.primeiros_socorros + self.secoes.primeiros_socorros.orientacoes_gerais + self.secoes.primeiros_socorros.notas_ao_medico),
            ('10', self.secoes.incompatibilidades, self.secoes.incompatibilidades.incompatibilidades),
        ]:
            if not secao.encontrada and itens:
                raise ValueError('Seção não localizada não pode conter dados extraídos.')
            if not secao.encontrada and not any(p.secao == numero and p.motivo == 'secao_nao_localizada' for p in self.pendencias):
                raise ValueError('Seção não localizada exige pendência correspondente.')
        return self
