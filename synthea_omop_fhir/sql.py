"""Petits utilitaires SQL partagés.

Un identifiant SQL (nom de table/colonne) ne peut PAS être passé comme paramètre
lié (les `?`/`%s` sont pour les valeurs). Quand on doit injecter un identifiant
— toujours issu d'une constante interne, jamais d'un input utilisateur —, on le
valide puis on le quote, au lieu de l'interpoler brut. Aligne le code sur le
principe « no string interpolation » (audit, famille S1).
"""

from __future__ import annotations


def quote_ident(name: str) -> str:
    """Valide un identifiant SQL et le retourne double-quoté.

    Lève ``ValueError`` si le nom n'est pas un identifiant simple (lettres,
    chiffres, underscore, ne commençant pas par un chiffre).
    """
    if not name.isidentifier():
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return f'"{name}"'
