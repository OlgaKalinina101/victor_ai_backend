# This file is part of victor_ai_backend.
#
# victor_ai_backend is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# victor_ai_backend is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with victor_ai_backend. If not, see <https://www.gnu.org/licenses/>.

"""
Тестовый скрипт для проверки утечек памяти в EmotionRecognizer
"""

import gc
import time
import psutil
import os
from emotion_recognizer import EmotionRecognizer

def get_memory_usage():
    """Возвращает использование памяти процессом в MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def test_language_switching():
    """
    Тест: Переключение языков
    
    Если есть утечка - память будет расти с каждой итерацией
    Если утечки нет - память стабилизируется после 2-3 итераций
    """
    print("=" * 70)
    print("ТЕСТ: Переключение языков (проверка утечек памяти)")
    print("=" * 70)
    
    test_texts = {
        "ru": "Я очень рад тебя видеть, это замечательный день!",
        "en": "I am so happy to see you, this is a wonderful day!"
    }
    
    memory_snapshots = []
    
    print("\nИтерация | Язык | Память (MB) | Прирост (MB)")
    print("-" * 60)
    
    for i in range(10):
        # Переключаемся между языками
        lang = "ru" if i % 2 == 0 else "en"
        
        # Вызываем predict
        result = EmotionRecognizer.predict(test_texts[lang], lang=lang)
        
        # Принудительная сборка мусора
        gc.collect()
        time.sleep(0.5)  # Даем время на очистку
        
        # Замеряем память
        current_memory = get_memory_usage()
        memory_snapshots.append(current_memory)
        
        growth = current_memory - memory_snapshots[0] if memory_snapshots else 0
        
        print(f"{i+1:^9} | {lang:^4} | {current_memory:>11.2f} | {growth:>13.2f}")
        
        # Выводим топ эмоцию для проверки
        top_emotion = max(result, key=lambda x: x['score'])
        print(f"           └─> {top_emotion['label']}: {top_emotion['score']:.3f}")
    
    print("-" * 60)
    
    # Анализ результатов
    initial_memory = memory_snapshots[0]
    final_memory = memory_snapshots[-1]
    max_memory = max(memory_snapshots)
    
    print(f"\n📊 СТАТИСТИКА:")
    print(f"   Начальная память: {initial_memory:.2f} MB")
    print(f"   Конечная память:  {final_memory:.2f} MB")
    print(f"   Пиковая память:   {max_memory:.2f} MB")
    print(f"   Общий прирост:    {final_memory - initial_memory:.2f} MB")
    
    # Оценка утечки
    growth = final_memory - initial_memory
    
    print(f"\n🔍 ОЦЕНКА:")
    if growth < 10:
        print("   ✅ Утечки НЕТ - прирост в пределах нормы")
    elif growth < 50:
        print("   ⚠️  Небольшая утечка - требует мониторинга")
    else:
        print("   🔴 УТЕЧКА обнаружена - требуется исправление!")
        print(f"      При {len(memory_snapshots)} переключениях: +{growth:.2f} MB")
        print(f"      Экстраполяция на 100 переключений: +{growth * 100 / len(memory_snapshots):.2f} MB")
    
    print("=" * 70)

def test_repeated_predictions():
    """
    Тест: Многократные предсказания на одном языке
    
    Проверяет утечку GPU tensors и кэша
    """
    print("\n" + "=" * 70)
    print("ТЕСТ: Многократные предсказания (один язык)")
    print("=" * 70)
    
    test_text = "Я очень рад тебя видеть, это замечательный день!"
    memory_snapshots = []
    
    print("\nИтерация | Память (MB) | Прирост (MB)")
    print("-" * 45)
    
    for i in range(20):
        result = EmotionRecognizer.predict(test_text, lang="ru")
        
        if i % 5 == 0:  # Замеряем каждые 5 итераций
            gc.collect()
            time.sleep(0.3)
            current_memory = get_memory_usage()
            memory_snapshots.append(current_memory)
            
            growth = current_memory - memory_snapshots[0] if len(memory_snapshots) > 1 else 0
            print(f"{i+1:^9} | {current_memory:>11.2f} | {growth:>13.2f}")
    
    print("-" * 45)
    
    growth = memory_snapshots[-1] - memory_snapshots[0]
    print(f"\n📊 Прирост памяти за 20 итераций: {growth:.2f} MB")
    
    if growth < 5:
        print("   ✅ Утечки НЕТ")
    elif growth < 20:
        print("   ⚠️  Небольшая утечка")
    else:
        print("   🔴 УТЕЧКА обнаружена!")
    
    print("=" * 70)

if __name__ == "__main__":
    print("\n🧪 Запуск тестов на утечки памяти...")
    print("(Требуется установить psutil: pip install psutil)\n")
    
    try:
        # Тест 1: Переключение языков
        test_language_switching()
        
        # Тест 2: Многократные предсказания
        test_repeated_predictions()
        
        print("\n✅ Тесты завершены!")
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("Установите необходимые библиотеки:")
        print("  pip install psutil")
    except Exception as e:
        print(f"❌ Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()

