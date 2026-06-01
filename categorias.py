"""
Mapeamento de categorias por função orçamentária e palavras-chave no objeto do convênio.
"""

FUNCAO_PARA_CATEGORIA = {
    "10": "Saúde",
    "11": "Trabalho",
    "12": "Educação",
    "13": "Cultura",
    "14": "Direitos da Cidadania",
    "15": "Urbanismo",
    "16": "Habitação",
    "17": "Saneamento",
    "18": "Gestão Ambiental",
    "20": "Agricultura",
    "21": "Organização Agrária",
    "22": "Indústria",
    "25": "Energia",
    "26": "Transporte",
    "27": "Desporto e Lazer",
    "28": "Encargos Especiais",
    "04": "Administração",
    "06": "Segurança Pública",
    "08": "Assistência Social",
    "09": "Previdência Social",
}

PALAVRAS_CHAVE_CATEGORIA = {
    "Saúde": [
        "ubs", "unidade básica", "hospital", "saúde", "ambulatório", "posto de saúde",
        "hemodiálise", "maternidade", "caps", "upa", "equipamento médico",
        "medicamento", "diagnóstico", "vigilância sanitária", "sus",
    ],
    "Infraestrutura": [
        "pavimentação", "asfalto", "calçamento", "estrada", "ponte", "viaduto",
        "obra", "construção", "reforma", "drenagem", "galeria", "sarjeta",
        "iluminação", "esgoto", "abastecimento", "adutora", "cisterna",
        "barragem", "açude", "contenção", "encostas", "muro",
    ],
    "Educação": [
        "escola", "creche", "educação", "ensino", "quadra", "biblioteca",
        "laboratório", "sala de aula", "pré-escola", "alfabetização",
        "formação", "capacitação", "bolsa",
    ],
    "Assistência Social": [
        "assistência social", "cras", "creas", "vulnerabilidade", "idoso",
        "criança", "adolescente", "família", "bolsa", "benefício", "abrigo",
        "proteção social", "pessoa com deficiência", "mulher", "igualdade",
    ],
    "Agricultura": [
        "agricultura", "agropecuária", "irrigação", "piscicultura", "aquicultura",
        "reforma agrária", "assentamento", "cooperativa", "rural", "produtor",
        "semente", "calcário", "adubo", "máquina agrícola", "trator",
    ],
    "Saneamento": [
        "saneamento", "água potável", "esgotamento sanitário", "resíduo",
        "aterro", "lixo", "abastecimento de água", "tratamento de água",
        "poço artesiano", "dessalinização",
    ],
    "Cultura e Esporte": [
        "cultura", "esporte", "lazer", "quadra poliesportiva", "ginásio",
        "praça", "parque", "teatro", "museu", "turismo", "patrimônio",
    ],
    "Segurança Pública": [
        "segurança", "policia", "bombeiro", "defesa civil", "videomonitoramento",
        "iluminação pública", "câmera",
    ],
}


def categorizar(funcao_codigo: str, objeto: str) -> str:
    if funcao_codigo and funcao_codigo in FUNCAO_PARA_CATEGORIA:
        cat_funcao = FUNCAO_PARA_CATEGORIA[funcao_codigo]
        if cat_funcao not in ("Encargos Especiais", "Administração"):
            return cat_funcao

    if objeto:
        texto = objeto.lower()
        for categoria, palavras in PALAVRAS_CHAVE_CATEGORIA.items():
            for palavra in palavras:
                if palavra in texto:
                    return categoria

    if funcao_codigo and funcao_codigo in FUNCAO_PARA_CATEGORIA:
        return FUNCAO_PARA_CATEGORIA[funcao_codigo]

    return "Outros"
