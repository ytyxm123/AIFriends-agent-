import {defineStore} from "pinia"
import {reactive, ref} from "vue";

export const useUserStore = defineStore('user',()=>{
    const id = ref()
    const username = ref('')
    const photo = ref('')
    const profile = ref('')
    const accessToken = ref('')

    const HasPullInfo = ref(false)
    function  isLogin()
    {
        return !!accessToken.value
    }
    function setAccessToken(Token){
        accessToken.value = Token
    }
    function setUserInfo(data){
        id.value = data.user_id
        username.value = data.username
        photo.value = data.photo
        profile.value = data.profile
    }

    function setHasPullInfo(hasPullInfo){
        HasPullInfo.value = hasPullInfo
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
        setHasPullInfo,
        HasPullInfo
    }
    })