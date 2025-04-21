from auth_afip import obtener_token_y_sign

token, sign = obtener_token_y_sign()
print("Token:", token)
print("Sign:", sign)
