from scraper.engine import ScraperEngine
from scraper.providers import get_provider_class, PROVIDER_REGISTRY

print("Available universities:")
print(list(PROVIDER_REGISTRY.keys()))

ProviderClass = get_provider_class("keio_university")
if not ProviderClass:
    raise Exception("Provider not found")

provider = ProviderClass()
engine = ScraperEngine(provider)
engine.run()