def slow_then_peck(z_from: float, z_to: float, z_clear: float,
                   feed_approach: int, feed_drill: int,
                   peck_step: float, peck_retract: float) -> list[str]:
    """
    Genereer G-code regels voor: langzaam aanboren, daarna peck-drill tot z_to.
    Voorbeeld: z_from=45, z_to=-2, z_clear=55
    """
    g = []
    # Aanboren
    g += [f"G0 Z{z_from:.3f}",
          f"G1 Z{z_from-2:.3f} F{feed_approach}"]
    # Peck
    z = z_from-2
    while z > z_to:
        nxt = max(z - peck_step, z_to)
        g += [f"G1 Z{nxt:.3f} F{feed_drill}",  # boren
              f"G0 Z{nxt+peck_retract:.3f}",   # klein terug
              f"G1 Z{nxt:.3f} F{feed_drill}"]  # weer in
        z = nxt
    # Uit
    g += [f"G0 Z{z_from:.3f}"]
    return g
