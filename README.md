# Abstract

## 🎥 Видеообзор настройки и работы
[тык](https://youtu.be/F2Y86CyzYbI)

## 📦 Модули

- **Abstact Registration** 
- **Bridge** 
- **Connect Twitter** 
- **Connect Discord** 
- **Swap** 
- **Vote** 
- **Claim Badges** 

## 🐍 Требования

- Python 3.12

## ⚙️ Установка

```sh
# Клонируем репозиторий
git clone https://github.com/saniksin/abstract.git
cd abstract

# Устанавливаем зависимости
pip install -r requirements.txt
```

## 🔧 Конфигурация

```sh
# Создаём .env-файл на основе примера
cp .env_example .env
```
- Заполните `.env` своими конфигурационными данными.
- Запустите проект для создания недостающих файлов:

```sh
python main.py
```

## 📂 Настройка файлов

Поместите необходимые файлы в папку `import`:
- **proxies.txt** (**обязательно**): `http://login:password@ip:port`
- **evm_pks.txt** (**обязательно**): приватные ключи Ethereum.
  - Для зашифрованных ключей добавьте **файл с солью** в папку `status`.
  - Зашифровать ключи можно с помощью [Crypto-Mate](https://github.com/saniksin/crypto-mate).

## 🚀 Использование

```sh
python main.py
```

## 🔧 Дополнительные зависимости

```sh
playwright install
```
