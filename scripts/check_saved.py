import os
import win32api
import win32con
import win32security

fpath = r"C:\Users\MONSTER\Downloads\Football Player Analysis-4_Final.pbix"
if os.path.exists(fpath):
    # Attributes
    attrs = win32api.GetFileAttributes(fpath)
    is_readonly = bool(attrs & win32con.FILE_ATTRIBUTE_READONLY)
    print(f"File: {fpath}")
    print(f"  Read-Only: {is_readonly}")
    print(f"  Hidden: {bool(attrs & win32con.FILE_ATTRIBUTE_HIDDEN)}")
    
    # Permissions (ACL)
    try:
        sd = win32security.GetFileSecurity(fpath, win32security.DACL_SECURITY_INFORMATION)
        dacl = sd.GetSecurityDescriptorDacl()
        print(f"  DACL entries: {dacl.GetAceCount() if dacl else 0}")
    except Exception as e:
        print(f"  ACL error: {e}")
else:
    print(f"File not found: {fpath}")
