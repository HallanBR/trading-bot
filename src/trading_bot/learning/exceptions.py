"""Erros seguros produzidos pela persistência de aprendizado."""


class LearningPersistenceError(RuntimeError):
    """Falha ao salvar ou consultar os exemplos de aprendizado."""
