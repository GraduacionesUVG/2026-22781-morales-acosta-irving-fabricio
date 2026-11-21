"""Sistema de reservas de salas de estudio.
Los horarios se manejan como enteros: las 9:30 se representa como 930.
"""

SALAS = {
    "A1": {"capacidad": 4, "apertura": 700, "cierre": 2100},
    "B2": {"capacidad": 8, "apertura": 700, "cierre": 2100},
    "C3": {"capacidad": 12, "apertura": 900, "cierre": 1800},
}

reservas = []


def _a_minutos(hora):
    """Convierte 930 -> 570 (minutos desde medianoche)."""
    return (hora // 100) * 60 + (hora % 100)


def _choca(ini1, fin1, ini2, fin2):
    """True si dos bloques [ini, fin) se traslapan (en minutos)."""
    return _a_minutos(ini1) < _a_minutos(fin2) and _a_minutos(ini2) < _a_minutos(fin1)


def agregar_reserva(sala, inicio, fin):
    """Registra una reserva si la sala existe, está dentro del horario
    de la sala y no choca con otra reserva activa. Devuelve el id o None."""
    if sala not in SALAS:
        return None
    datos = SALAS[sala]
    if inicio < datos["apertura"] or fin > datos["cierre"]:
        return None
    for r in reservas:
        if r["sala"] == sala and r["activa"] and _choca(inicio, fin, r["inicio"], r["fin"]):
            return None
    nuevo_id = len(reservas) + 1
    reservas.append({"id": nuevo_id, "sala": sala, "inicio": inicio,
                      "fin": fin, "activa": True})
    return nuevo_id


def cancelar_reserva(id_reserva):
    """Desactiva la reserva con ese id. Devuelve True si la encontró."""
    for r in reservas:
        if r["id"] == id_reserva and r["activa"]:
            r["activa"] = False
            return True
    return False


def reservas_de_sala(sala):
    """Lista de reservas activas de una sala, ordenadas por hora de inicio."""
    activas = [r for r in reservas if r["sala"] == sala and r["activa"]]
    return sorted(activas, key=lambda r: _a_minutos(r["inicio"]))


def _poblar_estado_inicial():
    """Inyecta el estado inicial necesario para que los 3 asserts de la
    tarea sean verificables: A1 reservada 8:00-10:00 y 11:30-13:00;
    C3 reservada 9:00-17:00; B2 queda libre. El participante NUNCA ve
    esta función ni su llamada: se ejecuta antes de servir el editor,
    como parte del arranque de la tarea procedimental (ver runner.py).
    """
    reservas.clear()
    agregar_reserva("A1", 800, 1000)
    agregar_reserva("A1", 1130, 1300)
    agregar_reserva("C3", 900, 1700)
