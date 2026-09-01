<script setup>

import {ref} from "vue";
import api from "@/js/http/api.js";
import {useUserStore} from "@/stores/user.js";
import {useRouter} from "vue-router";

const username = ref('')
const password = ref('')
const confirmedPassword  = ref('')
const error_message = ref('')

const user = useUserStore()
const router = useRouter()

async function register() {
  error_message.value = '';
  if (!username.value.trim()) {
      error_message.value = '用户名不能为空';
  }else if(!password.value.trim()) {
    error_message.value = '密码不能为空'
  }else if(confirmedPassword.value.trim()!==password.value.trim()) {
    error_message.value = '两次输入密码不一致'
  }
  else{
    try{
        const res =await api.post("api/user/register/", {
          username: username.value,
          password: password.value,
        })
      const data = res.data
      console.log(data)
      if(data.result ==='success'){

        user.setAccessToken(data.access)

        user.setUserInfo(data)

       await router.push({
          name:'homepage-index',
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
          <form @submit.prevent="register" class="fieldset bg-base-200 border-base-300 rounded-box w-xs border p-4">
          <label class="label">用户名</label>
          <input v-model="username" type="text" class="input" placeholder="请输入用户名" />

          <label class="label">密码</label>
          <input v-model="password" type="password" class="input" placeholder="请输入密码" />
            <label class="label">确认密码</label>
          <input v-model="confirmedPassword" type="password" class="input" placeholder="请再次输入密码" />
          <button class="btn btn-neutral mt-4">注册</button>
            <p v-if="error_message" class="text-sm text-red-500">{{error_message}}</p>
          <div class="flex justify-end">
              <RouterLink :to="{name:'login-index'}"class=" btn btn-sm btn-ghost text-gray-500">去登录</RouterLink>
          </div>
        </form>

    </div>
</template>

<style scoped>

</style>