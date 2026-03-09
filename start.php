@TITLE InstallShield

echo Обновление пакетов
apt update && apt upgrade
clear

echo Установка screen
sudo apt install screen
clear

echo Создание скрина с сервером
screen -rd server
clear

echo Создание директории server
mkdir server
clear

echo Переход в директорию сервера
cd server
clear

echo Установка git для работы с базой данных
sudo apt install git
clear

echo Копирование обязательных файлов сервера (Ядро, Бибилеотеки)
git clone https://github.com/dixsin/linux-server
clear

echo Выдача прав скриптам
chmod +x ./start.sh && chmod +x bin/php7/bin/php
clear

echo ============================================
echo Сервер успешно установлен!
echo Для следующего запуска сервера переходите в его директорию cd server и запускайте скрипт старта ./start.sh
echo Сейчас же вы можете запустить сервер с помощью ./start.sh
echo После перезагрузки вашей виртуальной машины нужно создать скрин screen -S "NAME" и запустить сервер
echo Если же у вас уже запущен сервер можете вернутся к его управлению с помощью команды screen -rd "NAME"
echo Сейчас название скрина: server.
echo Автор сие чуда: vk.com/dixsin
echo ============================================

exit