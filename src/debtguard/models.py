from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Finding:
    archivo: str
    linea: int
    funcion: str | None
    familia: str  # complejidad | regla | clon | satd
    regla: str
    severidad: str  # baja | media | alta | critica
    valor: float
    umbral: float | None = None
    costo_min: float = 0.0
    categoria: str | None = None  # estilo | mantenibilidad | seguridad
    valor_previo: float | None = None
    detalle: str = ""


@dataclass
class ChangeSet:
    caso_id: str
    origen: str
    modelo: str | None
    ruta_repo: str
    base_rev: str
    archivos: dict[str, list[int]] = field(default_factory=dict)
    lineas_anadidas: int = 0
    lineas_eliminadas: int = 0
    excluidos: list[str] = field(default_factory=list)

    @property
    def kloc_cambiadas(self) -> float:
        return self.lineas_anadidas / 1000


@dataclass
class Assessment:
    caso_id: str
    origen: str
    modelo: str | None
    kloc_cambiadas: float
    metricas: dict
    hallazgos: list[Finding]
    deuda_min: float
    deuda_horas: float
    horas_kloc: float
    debt_ratio: float
    nota_sqale: str
    ird: float | None
    veredicto: str
    versiones: dict
    errores: list[str] = field(default_factory=list)
    excluidos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
