' Launch start_all.bat silently (no visible window).
' Used by the Windows Startup shortcut so the bot starts at login
' without a black console popping up.
Set sh = CreateObject("WScript.Shell")
fn = WScript.ScriptFullName
folder = Left(fn, InStrRev(fn, "\"))
sh.CurrentDirectory = folder
sh.Run """" & folder & "start_all.bat""", 0, False
