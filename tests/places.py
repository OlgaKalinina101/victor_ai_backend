from tools.places.places_tool import PlacesContextBuilder

lat=55.8542525
lon=37.3522809
places = PlacesContextBuilder(prompt_path="C:/Users/Alien/PycharmProjects/Victor_AI_Core/tools/places/places_prompt.yaml")
prompt = places.build(lat, lon)
print(prompt)