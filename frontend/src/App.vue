<script setup>
import NavBar from "@/components/navbar/NavBar.vue"
import {onMounted} from "vue";
import {useUserStore} from "@/stores/user.js";
import api from "@/js/http/api.js";
import {useRoute, useRouter} from "vue-router";
const user = useUserStore()
const router = useRouter();
const route = useRoute()
onMounted(async () => {
  try{
    const res = await api.get('api/user/getInfo/')
    const data = res.data
    if(data.result === "success"){
        user.setUserInfo(data)
    }
  }catch(error){
    console.log(error)
  }finally{
    user.setHasPullInfo(true)
    if(route.meta.needLogin && !user.isLogin())
    {
      await router.replace(//replace不能退后
          {
             name:'login-index',
          }
      )
    }
  }
})
</script>

<template>
  <NavBar>
    <RouterView/>
  </NavBar>
</template>

<style scoped>

</style>
