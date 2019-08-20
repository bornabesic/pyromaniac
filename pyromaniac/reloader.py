
from threading import Thread
import time
import sys
import os
import importlib
import gc
import inspect
import functools
from collections import defaultdict
import itertools

from .log import LOGGER


class Reloader(Thread):

    def __init__(self):
        super().__init__(daemon=True)
        self.mtime_cache = dict()
        self.name_class_cache = defaultdict(set)

    @staticmethod
    def walk_objects(to_visit, objects, visited, classes):
        for obj in to_visit:
            if id(obj) in visited:
                continue
            if classes is not None and type(obj) not in classes:
                continue

            visited[id(obj)] = None

            objects.append(obj)
            referents = gc.get_referents(obj)
            if referents:
                Reloader.walk_objects(referents, objects, visited, classes)

    @staticmethod
    def get_all_objects(classes=None):
        gc_objects = gc.get_objects()
        visited = {}
        objects = []

        visited = {
            id(gc_objects): None,
            id(objects): None,
            id(visited): None,
            id(classes): None
        }

        Reloader.walk_objects(gc_objects, objects, visited, classes)

        return objects

    @staticmethod
    def apply(f, obj, times):
        if times == 0:
            return obj

        return Reloader.apply(f, f(obj), times - 1)

    def get_changed_modules(self):
        for module_name, module in sys.modules.items():
            if not hasattr(module, "__file__") or module.__file__ is None or not os.path.exists(module.__file__):
                continue

            new_mtime = os.stat(module.__file__).st_mtime
            old_mtime = self.mtime_cache.get(module_name, 0)
            if new_mtime != old_mtime:
                self.mtime_cache[module_name] = new_mtime
                if old_mtime > 0:
                    yield module

    def get_module_classes(self, module):
        old_classes = [attr for attr in module.__dict__.values() if inspect.isclass(attr)]

        # Update the name-to-class cache
        for cls in old_classes:
            self.name_class_cache[cls.__qualname__].add(cls)

        return dict(self.name_class_cache)

    def tick(self):
        # Check which modules have changed
        changed_modules = list(self.get_changed_modules())
        if not changed_modules:
            return

        # Get potentially changed classes
        changed_classes = list(map(lambda m: self.get_module_classes(m), changed_modules))
        classes_to_check = set(Reloader.apply(itertools.chain.from_iterable, map(lambda d: d.values(), changed_classes), 2))

        # Get objects that need to be patched
        changed_objects = Reloader.get_all_objects(classes_to_check)
        instances = defaultdict(list)
        for module_classes_dict in changed_classes:
            for class_name, classes in module_classes_dict.items():
                instances[class_name] = [obj for obj in changed_objects if type(obj) in classes]

        # Reload the changed modules
        for module in changed_modules:
            try:
                new_module = importlib.reload(module)
                LOGGER.info(f"Module {module.__name__} reloaded.")
            except SyntaxError as e:
                LOGGER.error(f"Cannot reload module {module.__name__}: {e}")
                continue

            # Live-patch the methods of living objects
            classes = [attr for attr in new_module.__dict__.values() if inspect.isclass(attr)]
            for cls in classes:
                objs = instances[cls.__qualname__]
                if not objs: # Some classes may be added and they have no instances
                    continue
                methods = [(cls_attr_name, cls_attr) for cls_attr_name, cls_attr in cls.__dict__.items() if inspect.isfunction(cls_attr)]
                for obj in objs:
                    for method_name, method in methods:
                       setattr(obj, method_name, functools.partial(method, obj))

    def run(self):
        LOGGER.info("Started.")
        while True:
            time.sleep(1)
            self.tick()
