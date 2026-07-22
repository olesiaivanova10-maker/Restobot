// =====================================================================
// НАСТРОЙКИ СТРУКТУРЫ
// =====================================================================
var targetSheetNames = [
  "Прототип таблицы", 
  "Киса бар", 
  "Асьенда", 
  "Синичка",
  "Буфет"
]; 

var promoSheets = ["Киса бар", "Асьенда", "Синичка", "Буфет"];

var blockWidth = 3;   
var blockHeight = 15; 
var startRow = 1;     
var headerColor = "#FFFACD"; 
var defaultColWidths = [180, 200, 600]; 
var firstRowHeight = 38;                
var otherRowsHeight = 66;               

function autoClearMonthly() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var today = new Date();
  var currentMonth = today.getMonth();
  var currentYear = today.getFullYear();
  
  var allSheets = targetSheetNames.concat(["Доклад"]);
  
  allSheets.forEach(function(sheetName) {
    var sheet = ss.getSheetByName(sheetName);
    if (!sheet) return;
    
    var bWidth = (sheetName === "Доклад") ? 5 : 3;
    var maxCols = sheet.getMaxColumns();
    if (maxCols < bWidth) return;
    
    var headerRow = sheet.getRange(1, 1, 1, maxCols).getValues()[0];
    var blocksToDelete = [];
    
    // Ищем блоки, которые не принадлежат текущему месяцу
    for (var c = 0; c < maxCols; c += bWidth) {
      var dateVal = (sheetName === "Доклад") ? headerRow[c + 1] : headerRow[c + 2];
      if (dateVal instanceof Date) {
        if (dateVal.getMonth() !== currentMonth || dateVal.getFullYear() !== currentYear) {
          blocksToDelete.push(c + 1); // 1-based index для deleteColumns
        }
      }
    }
    
    // Удаляем блоки с конца (чтобы не сдвигались индексы)
    for (var i = blocksToDelete.length - 1; i >= 0; i--) {
      var colStart = blocksToDelete[i];
      if (sheet.getMaxColumns() <= bWidth) {
        // Нельзя удалить все колонки с листа, поэтому просто очищаем
        sheet.clear();
      } else {
        sheet.deleteColumns(colStart, bWidth);
      }
    }
  });
}

// =====================================================================
// ЛИСТЫ ЗАВЕДЕНИЙ: ГЕНЕРАЦИЯ ДНЕЙ
// =====================================================================
function generateNextDayBlock() {
  autoClearMonthly();
  
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var today = new Date();
  today.setHours(0, 0, 0, 0);
  
  targetSheetNames.forEach(function(sheetName) {
    var sheet = ss.getSheetByName(sheetName);
    if (!sheet) return; 
    var currentBlockHeight = (sheetName === "Киса бар") ? 17 : blockHeight;
    
    var maxColumns = sheet.getMaxColumns();
    var lastColumnWithData = 0; 
    
    // ПАКЕТНОЕ ЧТЕНИЕ
    if (maxColumns >= 3) {
      var headerRow = sheet.getRange(startRow, 1, 1, maxColumns).getValues()[0];
      for (var col = 0; col < maxColumns; col += blockWidth) {
        if (col + 2 < headerRow.length && headerRow[col + 2] instanceof Date) {
          lastColumnWithData = col + 1;
        }
      }
    }
    
    var checkDate = new Date();
    if (lastColumnWithData > 0) {
      var lastDateInTable = sheet.getRange(startRow, lastColumnWithData + 2).getValue();
      checkDate = new Date(lastDateInTable);
      checkDate.setHours(0, 0, 0, 0);
    } else {
      checkDate = new Date(today);
      checkDate.setDate(today.getDate() - 1);
      checkDate.setHours(0, 0, 0, 0);
    }
    
    var safetyCounter = 0;
    while (checkDate < today && safetyCounter < 30) {
      safetyCounter++;
      
      var targetColumn = (lastColumnWithData === 0) ? 1 : lastColumnWithData + blockWidth;
      var nextDate = new Date(checkDate);
      nextDate.setDate(nextDate.getDate() + 1);
      nextDate.setHours(0, 0, 0, 0);
      
      var tomorrowDate = new Date(nextDate);
      tomorrowDate.setDate(tomorrowDate.getDate() + 1);
      
      var currentMaxCols = sheet.getMaxColumns();
      var neededCols = targetColumn + blockWidth - 1;
      if (neededCols > currentMaxCols) {
        sheet.insertColumnsAfter(currentMaxCols, neededCols - currentMaxCols);
      }
      
      var targetRange = sheet.getRange(startRow, targetColumn, currentBlockHeight, blockWidth);
      
      // Правильное снятие объединений
      var mergedRanges = targetRange.getMergedRanges();
      for (var m = 0; m < mergedRanges.length; m++) {
        mergedRanges[m].breakApart();
      }
      
      targetRange.clearContent();
      
      for (var w = 0; w < blockWidth; w++) {
        sheet.setColumnWidth(targetColumn + w, defaultColWidths[w]);
      }
      
      for (var h = 0; h < currentBlockHeight; h++) {
        sheet.setRowHeight(startRow + h, (h === 0 || h === 5) ? firstRowHeight : otherRowsHeight);
      }
      
      var blockValues = [
        ["Открытие", "", nextDate],
        ["Стоп лист", "", ""],
        ["Приход продуктов", "", ""],
        ["Приход хозов", "", ""],
        ["Доклад об открытии смены", "", ""],
        ["Закрытие", "", nextDate],
        ["Наличные", "", ""],
        ["Безнал", "", ""],
        ["Общая выручка", "", ""],
        ["Количество гостей", "", ""],
        ["Опасные операции", "", ""],
        ["Блюда за счет заведения", "", ""],
        ["Расходы на маркетинг", "", ""],
        ["Расходы на смену", "", ""],
        ["Доклад о закрытии смены", "", ""]
      ];
      if (sheetName === "Киса бар") {
        blockValues.splice(8, 0, ["Депозиты", "", ""]);
        blockValues.splice(15, 1);
        blockValues.splice(14, 0, ["Доклад о закрытии смены", "", ""]);
        blockValues.push(["Медуза", "", ""]);
      }
      targetRange.setValues(blockValues);
      
      targetRange.setFontFamily("Montserrat").setFontSize(10).setFontWeight("normal").setWrap(true);
      targetRange.setHorizontalAlignment("left").setVerticalAlignment("middle");
      
      sheet.getRange(startRow, targetColumn).setBackground(headerColor).setFontSize(13);
      sheet.getRange(startRow + 5, targetColumn).setBackground(headerColor).setFontSize(13);
      
      var date1 = sheet.getRange(startRow, targetColumn + 2, 1, 1);
      var date2 = sheet.getRange(startRow + 5, targetColumn + 2, 1, 1);
      date1.setHorizontalAlignment("center").setVerticalAlignment("middle").setFontSize(14).setNumberFormat('dd.MM').setFontWeight("bold");
      date2.setHorizontalAlignment("center").setVerticalAlignment("middle").setFontSize(14).setNumberFormat('dd.MM').setFontWeight("bold");
      
      sheet.getRange(startRow + 1, targetColumn, 4, 1).setFontSize(13);
      sheet.getRange(startRow + 6, targetColumn, currentBlockHeight - 6, 1).setFontSize(13);
      
      try {
        for (var r = 2; r <= 5; r++) sheet.getRange(startRow + r - 1, targetColumn + 1, 1, 2).mergeAcross().setFontSize(13);
        for (var r = 7; r <= currentBlockHeight; r++) sheet.getRange(startRow + r - 1, targetColumn + 1, 1, 2).mergeAcross().setFontSize(13);
      } catch (e) {}
      
      targetRange.setBorder(true, true, true, true, false, false, "black", SpreadsheetApp.BorderStyle.MEDIUM);
      sheet.getRange(startRow, targetColumn, 5, 1).setBorder(true, true, true, true, false, false, "black", SpreadsheetApp.BorderStyle.MEDIUM);
      sheet.getRange(startRow + 5, targetColumn, currentBlockHeight - 5, 1).setBorder(true, true, true, true, false, false, "black", SpreadsheetApp.BorderStyle.MEDIUM);
      
      // Границы для ячеек B1:C1 и B6:C6
      sheet.getRange(startRow, targetColumn + 1, 1, 2).setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.MEDIUM);
      sheet.getRange(startRow + 5, targetColumn + 1, 1, 2).setBorder(true, true, true, true, true, true, "black", SpreadsheetApp.BorderStyle.MEDIUM);
      
      lastColumnWithData = targetColumn;
      checkDate = nextDate;
    }
    
    // АВТОУДАЛЕНИЕ ПУСТЫХ СТРОК И СТОЛБЦОВ
    var totalNeededCols = (lastColumnWithData === 0) ? blockWidth : lastColumnWithData + blockWidth - 1;
    trimSheet(sheet, startRow + currentBlockHeight - 1, totalNeededCols);
  });
}

// =====================================================================
// ЛИСТ СВОДНОГО ДОКЛАДА: ГЕНЕРАЦИЯ И СБОР ДАННЫХ
// =====================================================================
function generateReportBlock() {
  autoClearMonthly();

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Доклад");
  if (!sheet) return;
  
  var repBlockWidth = 5;
  var repBlockHeight = 11; // Было 12, теперь 11 (названия ресторанов в 1 строке)
  var repColWidths = [154, 350, 350, 350, 350];
  
  var maxColumns = sheet.getMaxColumns();
  var lastColumnWithData = 0;
  
  if (maxColumns >= repBlockWidth) {
    var headerRow = sheet.getRange(startRow, 1, 1, maxColumns).getValues()[0];
    for (var col = 0; col < maxColumns; col += repBlockWidth) {
      // Ищем дату в колонке A (индекс col)
      var cellVal = headerRow[col];
      if (cellVal) {
        lastColumnWithData = col + 1;
      }
    }
  }
  
  var today = new Date();
  today.setHours(0, 0, 0, 0);
  
  var targetColumn = (lastColumnWithData === 0) ? 1 : lastColumnWithData + repBlockWidth;
  var checkDate = new Date();
  if (lastColumnWithData > 0) {
    var lastDateInTable = sheet.getRange(startRow, lastColumnWithData).getValue(); // Ячейка A1
    
    // Если там строка 'dd.MM', попробуем спарсить (в текущем году)
    if (typeof lastDateInTable === "string" && lastDateInTable.includes(".")) {
      var parts = lastDateInTable.split(".");
      checkDate = new Date(today.getFullYear(), parseInt(parts[1])-1, parseInt(parts[0]));
    } else {
      checkDate = new Date(lastDateInTable);
    }
    checkDate.setHours(0, 0, 0, 0);
  } else {
    checkDate = new Date(today);
    checkDate.setDate(today.getDate() - 1);
    checkDate.setHours(0, 0, 0, 0);
  }
  
  if (checkDate && checkDate.getTime() === today.getTime()) {
    targetColumn = lastColumnWithData; 
  } else {
    while (checkDate < today) {
      var repNextDate = new Date(checkDate);
      repNextDate.setDate(repNextDate.getDate() + 1);
      repNextDate.setHours(0, 0, 0, 0);
      
      var repTomorrowDate = new Date(repNextDate);
      repTomorrowDate.setDate(repTomorrowDate.getDate() + 1);
      repTomorrowDate.setHours(0, 0, 0, 0);
      
      var currentMaxCols = sheet.getMaxColumns();
      var neededCols = targetColumn + repBlockWidth - 1;
      if (neededCols > currentMaxCols) {
        sheet.insertColumnsAfter(currentMaxCols, neededCols - currentMaxCols);
      }
      
      var targetRange = sheet.getRange(startRow, targetColumn, repBlockHeight, repBlockWidth);
      
      // Правильное снятие объединений
      var mergedRanges = targetRange.getMergedRanges();
      for (var m = 0; m < mergedRanges.length; m++) {
        mergedRanges[m].breakApart();
      }
      targetRange.clearContent();
      
      for (var w = 0; w < repBlockWidth; w++) sheet.setColumnWidth(targetColumn + w, repColWidths[w]);
      for (var h = 0; h < repBlockHeight; h++) {
        sheet.setRowHeight(startRow + h, (h < 1) ? 40 : otherRowsHeight);
      }
      
      var repValues = [
        [repNextDate, promoSheets[0], promoSheets[1], promoSheets[2], promoSheets[3]],
        ["Открытие", "", "", "", ""],
        ["Стоп лист", "", "", "", ""],
        ["Закрытие", "", "", "", ""],
        ["Выручка", "", "", "", ""],
        ["Наличные", "", "", "", ""],
        ["Безнал", "", "", "", ""],
        ["Гостей", "", "", "", ""],
        ["Расходы на смену", "", "", "", ""],
        ["За счет заведения", "", "", "", ""],
        ["Опасные", "", "", "", ""]
      ];
      targetRange.setValues(repValues);
      
      targetRange.setFontFamily("Montserrat").setFontSize(10).setFontWeight("normal").setWrap(true);
      targetRange.setHorizontalAlignment("left").setVerticalAlignment("middle");
      
      // Форматирование заголовков
      sheet.getRange(startRow, targetColumn).setNumberFormat('dd.MM').setHorizontalAlignment("center").setFontWeight("bold").setFontSize(14).setBackground(headerColor);
      sheet.getRange(startRow, targetColumn + 1, 1, 4).setHorizontalAlignment("center").setFontWeight("bold").setFontSize(12).setBackground(headerColor);
      
      // Очистка фона для области данных (B2:E11)
      sheet.getRange(startRow + 1, targetColumn + 1, 10, 4).setBackground(null);
      
      // Оформление колонок A
      sheet.getRange(startRow + 1, targetColumn, 10, 1).setFontSize(11).setFontWeight("bold");
      
      // Границы
      // B2:E11
      sheet.getRange(startRow + 1, targetColumn + 1, 10, 4).setBorder(true, true, true, true, false, false, "black", SpreadsheetApp.BorderStyle.MEDIUM);
      // A2:A11
      sheet.getRange(startRow + 1, targetColumn, 10, 1).setBorder(true, true, true, true, false, false, "black", SpreadsheetApp.BorderStyle.MEDIUM);
      // B1:E1
      sheet.getRange(startRow, targetColumn + 1, 1, 4).setBorder(true, true, true, true, false, false, "black", SpreadsheetApp.BorderStyle.MEDIUM);
      // A1
      sheet.getRange(startRow, targetColumn, 1, 1).setBorder(true, true, true, true, false, false, "black", SpreadsheetApp.BorderStyle.MEDIUM);
      
      // Сдвигаем дату и колонку для следующей итерации цикла
      lastColumnWithData = targetColumn;
      checkDate = new Date(repNextDate);
      targetColumn += repBlockWidth;
    }
  }
  
  // ПАКЕТНЫЙ СБОР ДАННЫХ ИЗ ЛИСТОВ ЗАВЕДЕНИЙ
  var currentMaxReportCols = sheet.getMaxColumns();
  var reportHeadersRow = sheet.getRange(startRow, 1, 1, currentMaxReportCols).getValues()[0];
  
  for (var col = 0; col < currentMaxReportCols; col += repBlockWidth) {
    if (col >= reportHeadersRow.length) continue;
    var blockDateRaw = reportHeadersRow[col];
    if (!blockDateRaw) continue;
    
    var blockDate = new Date(blockDateRaw);
    if (typeof blockDateRaw === "string" && blockDateRaw.includes(".")) {
        var p = blockDateRaw.split(".");
        blockDate = new Date(today.getFullYear(), parseInt(p[1])-1, parseInt(p[0]));
    }
    blockDate.setHours(0,0,0,0);
    
    var rRange = sheet.getRange(startRow, col + 1, repBlockHeight, repBlockWidth);
    var reportBlockValues = rRange.getValues(); 
    
    promoSheets.forEach(function(sName, index) {
      var sourceSheet = ss.getSheetByName(sName);
      if (!sourceSheet) return;
      var sMaxCols = sourceSheet.getMaxColumns();
      if (sMaxCols < 3) return;
      
      var sourceHeaderRow = sourceSheet.getRange(startRow, 1, 1, sMaxCols).getValues()[0];
      var sourceColIndex = -1;
      
      for (var sCol = 0; sCol < sMaxCols; sCol += blockWidth) {
        if (sCol + 2 < sourceHeaderRow.length) {
          var sDateRaw = sourceHeaderRow[sCol + 2];
          if (!sDateRaw) continue;
          
          var sDate = new Date(sDateRaw);
          if (typeof sDateRaw === "string" && sDateRaw.includes(".")) {
             var p = sDateRaw.split(".");
             sDate = new Date(today.getFullYear(), parseInt(p[1])-1, parseInt(p[0]));
          }
          sDate.setHours(0,0,0,0);
          
          if (sDate.getTime() === blockDate.getTime()) {
            sourceColIndex = sCol + 1;
            break;
          }
        }
      }
      
      if (sourceColIndex !== -1) {
        var sourceBlockHeight = (sName === "Киса бар") ? 17 : blockHeight;
        var srcData = sourceSheet.getRange(startRow, sourceColIndex, sourceBlockHeight, blockWidth).getDisplayValues();
        
        // Данные Открытия, Стоп-листа, Закрытия и финансов — всё из ТЕКУЩЕГО блока
        reportBlockValues[1][1 + index] = srcData[0][1]; // Открытие (Время)
        reportBlockValues[2][1 + index] = srcData[1][1]; // Стоп лист
        reportBlockValues[4][1 + index] = srcData[8][1]; // Выручка
        reportBlockValues[7][1 + index] = srcData[9][1]; // Гостей
        reportBlockValues[5][1 + index] = srcData[6][1]; // Наличные
        reportBlockValues[6][1 + index] = srcData[7][1]; // Безнал
        reportBlockValues[3][1 + index] = srcData[5][1]; // Закрытие (Время)
        reportBlockValues[10][1 + index] = srcData[10][1]; // Опасные
        reportBlockValues[9][1 + index] = srcData[11][1]; // За счет
        var expensesRowIndex = (sName === "Киса бар") ? 15 : 13;
        reportBlockValues[8][1 + index] = srcData[expensesRowIndex][1]; // Расходы на смену
      }
    });
    
    rRange.setValues(reportBlockValues);
  }
  
  // АВТОУДАЛЕНИЕ
  var totalRepNeededCols = (lastColumnWithData === 0) ? repBlockWidth : lastColumnWithData + repBlockWidth - 1;
  trimSheet(sheet, startRow + repBlockHeight - 1, totalRepNeededCols);
}

// =====================================================================
// УТИЛИТЫ И ТРИГГЕРЫ
// =====================================================================

function trimSheet(sheet, neededRows, neededCols) {
  var maxRows = sheet.getMaxRows();
  if (maxRows > neededRows) {
    sheet.deleteRows(neededRows + 1, maxRows - neededRows);
  }
  var maxCols = sheet.getMaxColumns();
  if (maxCols > neededCols) {
    sheet.deleteColumns(neededCols + 1, maxCols - neededCols);
  }
}

function syncAllDates() {
  // Вызывает полную синхронизацию (генерация блоков и сбор)
  generateReportBlock();
}

function onOpen() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  
  // Находим последнюю колонку с данными
  var lastCol = sheet.getLastColumn();
  
  // Если таблица не пустая, переходим к самой правой ячейке первой строки
  if (lastCol > 0) {
    var targetCell = sheet.getRange(1, lastCol);
    sheet.setActiveCell(targetCell);
  }
}
