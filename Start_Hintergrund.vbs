' Datei-Suchmaschine Pro - Start ohne Konsolenfenster
'   wscript Start_Hintergrund.vbs          -> Server unsichtbar starten (Autostart)
'   wscript Start_Hintergrund.vbs open     -> Server starten (falls noetig) + Browser oeffnen
Set WshShell = CreateObject("WScript.Shell")
Set Fso = CreateObject("Scripting.FileSystemObject")
WshShell.CurrentDirectory = Fso.GetParentFolderName(WScript.ScriptFullName)

Function ServerLaeuft()
    Set oExec = WshShell.Exec("cmd /c netstat -ano | findstr "":5005"" | findstr ""LISTENING""")
    ServerLaeuft = (Len(Trim(oExec.StdOut.ReadAll())) > 0)
End Function

If Not ServerLaeuft() Then
    ' Window-Style 0 = unsichtbar; --no-browser verhindert doppeltes Browser-Oeffnen
    WshShell.Run "python app.py --no-browser", 0, False
    WScript.Sleep 3000
End If

If WScript.Arguments.Count > 0 Then
    If LCase(WScript.Arguments(0)) = "open" Then
        WshShell.Run "http://localhost:5005", 1, False
    End If
End If
