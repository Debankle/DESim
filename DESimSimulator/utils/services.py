# source: ChatGPT as a better alternative to multiclass singletons
#
# Goal is to pull secrets and parameters once per launch, would
# be better to cache them but i'm too lazy and they won't change
# during running for this use case

from typing import TypeVar, cast

T = TypeVar("T")

_services: dict[str, object] = {}


def register_service(name: str, instance: object):
    _services[name] = instance


def get_service(name: str, type_: type[T]) -> T:
    return cast(T, _services[name])
