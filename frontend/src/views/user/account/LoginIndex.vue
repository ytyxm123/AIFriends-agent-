<script setup >
import {useUserStore} from "@/stores/user";
import {ref} from "vue";
import {useRouter} from "vue-router";
import api from "@/js/http/api.js";

const user = useUserStore()
const username = ref('')
const password = ref('')
const error_message = ref('')
const router = useRouter()

async function login() {
  error_message.value = '';
  if (!username.value.trim()) {
      error_message.value = '用户名不能为空';
  }else if(!password.value.trim()) {
    error_message.value = '密码不能为空'
  }else{
    try{
        const res =await api.post("api/user/login/", {
          username: username.value,
          password: password.value
        })
      const data = res.data
      if(data.result ==='success'){
        user.setAccessToken(data.access)
        user.setUserInfo(data)
       await router.push({
          name:'homepage-index'
        })
      }
      else{
        error_message.value = data.result
      }
    }catch (err){
      console.log(err)
    }
  }
}
</script>

<template>
    <div class="flex justify-center mt-30">
          <form @submit.prevent="login" class="fieldset bg-base-200 border-base-300 rounded-box w-xs border p-4">
          <label class="label">用户名</label>
          <input v-model="username" type="text" class="input" placeholder="请输入用户名" />

          <label class="label">密码</label>
          <input v-model="password" type="password" class="input" placeholder="请输入密码" />

            <p v-if="error_message" class="text-sm text-red-500 mt-1">{{error_message}}</p>

          <button class="btn btn-neutral mt-4">登录</button>
          <div class="flex justify-end">
              <RouterLink :to="{name:'register-index'}"class=" btn btn-sm btn-ghost text-gray-500">注册</RouterLink>
          </div>
        </form>
    </div>
</template>

<style scoped>

</style>