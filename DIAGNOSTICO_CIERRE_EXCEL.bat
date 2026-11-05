@echo off
setlocal
set "SAR_DIAG_REPORT=%~dp0Diagnostico_Excel.txt"
> "%SAR_DIAG_REPORT%" echo DIAGNOSTICO DEL CIERRE DE MICROSOFT EXCEL
>> "%SAR_DIAG_REPORT%" echo Fecha de consulta: %DATE% %TIME%
>> "%SAR_DIAG_REPORT%" echo.
>> "%SAR_DIAG_REPORT%" echo VERSION DE OFFICE
reg query "HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration" /v VersionToReport >> "%SAR_DIAG_REPORT%" 2>&1
reg query "HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration" /v Platform >> "%SAR_DIAG_REPORT%" 2>&1
reg query "HKLM\SOFTWARE\Microsoft\Office\16.0\Outlook" /v Bitness >> "%SAR_DIAG_REPORT%" 2>&1
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\Office\16.0\Outlook" /v Bitness >> "%SAR_DIAG_REPORT%" 2>&1
>> "%SAR_DIAG_REPORT%" echo.
>> "%SAR_DIAG_REPORT%" echo ULTIMOS CIERRES DE EXCEL EN LOS ULTIMOS SIETE DIAS
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { $events=Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000,1001;StartTime=(Get-Date).AddDays(-7)}; $n=0; foreach($e in $events) { $d=@{}; foreach($x in ([xml]$e.ToXml()).Event.EventData.Data) { $d[$x.GetAttribute('Name')]=$x.InnerText }; $app=if($d.AppName){$d.AppName}else{$d.P1}; if([IO.Path]::GetFileName($app) -ine 'EXCEL.EXE'){continue}; $kind=if($e.Id -eq 1000){'Application Error'}else{$d.EventName}; $isCrash=$kind -match 'crash|BEX|Application Error'; $module=if($d.ModuleName){$d.ModuleName}elseif($isCrash){$d.P4}else{''}; $version=if($d.AppVersion){$d.AppVersion}else{$d.P2}; $code=if($d.ExceptionCode){$d.ExceptionCode}elseif($isCrash){$d.P7}else{''}; Write-Output ('Fecha: '+$e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')); Write-Output ('Evento: '+$e.Id); Write-Output ('Tipo: '+$kind); Write-Output ('Version de Excel: '+$version); Write-Output ('Modulo que falla: '+[IO.Path]::GetFileName($module)); Write-Output ('Version del modulo: '+$d.ModuleVersion); Write-Output ('Codigo de excepcion: '+$code); Write-Output ('Posicion del fallo: '+$d.FaultingOffset); Write-Output ''; $n++; if($n -ge 3){break} }; if($n -eq 0){Write-Output 'No se encontraron cierres de EXCEL.EXE en ese periodo.'} } catch { if($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*'){Write-Output 'No se encontraron eventos de fallo en ese periodo.'}else{Write-Output ('No se pudo consultar el registro de Windows: '+$_.Exception.Message)} }" >> "%SAR_DIAG_REPORT%" 2>&1
echo.
echo Se ha creado Diagnostico_Excel.txt en esta misma carpeta.
echo Adjunta ese archivo y el Excel recien generado que se cierra.
start "" notepad.exe "%SAR_DIAG_REPORT%"
endlocal
