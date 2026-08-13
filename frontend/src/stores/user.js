import {defineStore} from "pinia"
import {reactive, ref} from "vue";

export const useUserStore = defineStore('user',()=>{
    const id = ref(1)
    const username = ref("yxm")
    const photo = ref("http://127.0.0.1:8000/media/user/photo/default.png")
    const profile = ref("11")
    const accessToken = ref("11")
    function  isLogin()
    {
        return !!accessToken.value
    }
    function setAccessToken(accessToken){
        accessToken.value = accessToken
    }
    function setUserInfo(data){
        id.value = data.user_id
        username.value = data.username
        photo.value = data.phone
        profile.value = data.profile
    }
    function logout()
    {
        id.value = 0
        username.value = ""
        photo.value = ""
        accessToken.value = ""
        profile.value = ""
    }
    return {
        id,
        username,
        photo,
        accessToken,
        profile,
        isLogin,
        setAccessToken,
        setUserInfo,
        logout,
    }
    })