# Victor AI - Personal AI Companion for Android
# Copyright (C) 2025-2026 Olga Kalinina

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.

"""Репозиторий для работы с использованием моделей."""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from infrastructure.database.models import ModelUsage
from infrastructure.logging.logger import setup_logger

logger = setup_logger("model_usage_repository")


class ModelUsageRepository:
    """
    Репозиторий для работы с учётом использования моделей.
    
    Инкапсулирует логику работы с ModelUsage:
    - Обновление использования токенов
    - Получение статистики использования
    - Расчёт затрат
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def update_usage(
        self,
        account_id: str,
        model_name: str,
        provider: str,
        input_tokens: int,
        output_tokens: int
    ) -> ModelUsage:
        """
        Обновляет количество использованных токенов.
        
        Если запись для модели уже существует - обновляет её.
        Если нет - создаёт новую.
        
        Args:
            account_id: ID пользователя
            model_name: Название модели
            provider: Провайдер модели (OpenAI, Anthropic, etc)
            input_tokens: Количество входных токенов
            output_tokens: Количество выходных токенов
            
        Returns:
            Обновлённая или созданная запись ModelUsage
        """
        result = self.session.execute(
            select(ModelUsage).where(
                and_(
                    ModelUsage.account_id == account_id,
                    ModelUsage.model_name == model_name,
                    ModelUsage.provider == provider
                )
            )
        )
        usage = result.scalar_one_or_none()
        
        if usage:
            # Обновляем существующую запись
            usage.input_tokens_used += input_tokens
            usage.output_tokens_used += output_tokens
            logger.debug(f"Обновлено использование для {model_name}/{provider}: +{input_tokens} input, +{output_tokens} output")
        else:
            # Создаём новую запись
            usage = ModelUsage(
                account_id=account_id,
                model_name=model_name,
                provider=provider,
                input_tokens_used=input_tokens,
                output_tokens_used=output_tokens
            )
            self.session.add(usage)
            logger.info(f"Создана запись использования для {model_name}/{provider}")
        
        self.session.commit()
        self.session.refresh(usage)
        return usage
    
    def get_by_account_id(self, account_id: str) -> List[ModelUsage]:
        """
        Получает все записи использования моделей для пользователя.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Список записей ModelUsage
        """
        return self.session.query(ModelUsage).filter_by(account_id=account_id).all()
    
    def get_by_model(
        self,
        account_id: str,
        model_name: str,
        provider: Optional[str] = None
    ) -> Optional[ModelUsage]:
        """
        Получает запись использования конкретной модели.
        
        Args:
            account_id: ID пользователя
            model_name: Название модели
            provider: Провайдер (опционально)
            
        Returns:
            Запись ModelUsage или None
        """
        query = self.session.query(ModelUsage).filter_by(
            account_id=account_id,
            model_name=model_name
        )
        
        if provider:
            query = query.filter_by(provider=provider)
        
        return query.first()
    
    def get_total_tokens(self, account_id: str) -> dict:
        """
        Получает общее количество использованных токенов.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Словарь с общим количеством входных и выходных токенов
        """
        usages = self.get_by_account_id(account_id)
        
        total_input = sum(u.input_tokens_used for u in usages)
        total_output = sum(u.output_tokens_used for u in usages)
        
        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output
        }
    
    def get_usage_by_provider(self, account_id: str) -> dict:
        """
        Группирует использование по провайдерам.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Словарь {provider: {input_tokens, output_tokens}}
        """
        usages = self.get_by_account_id(account_id)
        
        result = {}
        for usage in usages:
            if usage.provider not in result:
                result[usage.provider] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "models": []
                }
            
            result[usage.provider]["input_tokens"] += usage.input_tokens_used
            result[usage.provider]["output_tokens"] += usage.output_tokens_used
            result[usage.provider]["models"].append({
                "name": usage.model_name,
                "input_tokens": usage.input_tokens_used,
                "output_tokens": usage.output_tokens_used
            })
        
        return result
    
    def reset_usage(self, account_id: str, model_name: str, provider: str) -> bool:
        """
        Сбрасывает статистику использования конкретной модели.
        
        Args:
            account_id: ID пользователя
            model_name: Название модели
            provider: Провайдер
            
        Returns:
            True если сброшено, False если не найдено
        """
        usage = self.get_by_model(account_id, model_name, provider)
        
        if not usage:
            logger.warning(f"Запись использования для {model_name}/{provider} не найдена")
            return False
        
        usage.input_tokens_used = 0
        usage.output_tokens_used = 0
        
        self.session.commit()
        logger.info(f"Сброшена статистика для {model_name}/{provider}")
        return True
    
    def delete_usage(self, account_id: str, model_name: str, provider: str) -> bool:
        """
        Удаляет запись использования модели.
        
        Args:
            account_id: ID пользователя
            model_name: Название модели
            provider: Провайдер
            
        Returns:
            True если удалено, False если не найдено
        """
        usage = self.get_by_model(account_id, model_name, provider)
        
        if not usage:
            logger.warning(f"Запись использования для {model_name}/{provider} не найдена")
            return False
        
        self.session.delete(usage)
        self.session.commit()
        
        logger.info(f"Удалена запись использования для {model_name}/{provider}")
        return True
    
    def get_all_aggregated(self, account_id: str = 'aggregated') -> List[ModelUsage]:
        """
        Получает агрегированную статистику по всем аккаунтам.
        
        Суммирует токены по каждой паре (model_name, provider) из всех аккаунтов.
        Баланс берет только с account_id='test_user'.
        
        Args:
            account_id: ID аккаунта для маркировки результата (по умолчанию 'aggregated')
        
        Returns:
            Список ModelUsage с агрегированными данными
        """
        from sqlalchemy import func
        
        # Агрегируем токены по model_name и provider
        result = self.session.query(
            ModelUsage.model_name,
            ModelUsage.provider,
            func.sum(ModelUsage.input_tokens_used).label('total_input'),
            func.sum(ModelUsage.output_tokens_used).label('total_output')
        ).group_by(
            ModelUsage.model_name,
            ModelUsage.provider
        ).all()
        
        # Получаем балансы и цены с test_user (эталонные значения)
        test_user_records = self.get_by_account_id('test_user')
        test_user_data = {
            (u.model_name, u.provider): {
                'balance': u.account_balance,
                'input_price': u.input_token_price,
                'output_price': u.output_token_price
            }
            for u in test_user_records
        }
        
        # Создаем агрегированные объекты
        aggregated = []
        for row in result:
            key = (row.model_name, row.provider)
            data = test_user_data.get(key, {'balance': 0.0, 'input_price': 0.0, 'output_price': 0.0})
            
            usage = ModelUsage(
                account_id=account_id,  # Используем переданный account_id
                model_name=row.model_name,
                provider=row.provider,
                input_tokens_used=row.total_input or 0,
                output_tokens_used=row.total_output or 0,
                input_token_price=data['input_price'],  # Цены с test_user (эталонные)
                output_token_price=data['output_price'],  # Цены с test_user (эталонные)
                account_balance=data['balance']  # Баланс с test_user
            )
            aggregated.append(usage)
        
        logger.info(f"Получена агрегированная статистика для account_id={account_id}: {len(aggregated)} записей")
        return aggregated

