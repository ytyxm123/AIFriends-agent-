<script setup lang="ts">

</script>

<template>
 <div class="flex justify-center mt-30">
          <fieldset class="fieldset bg-base-200 border-base-300 rounded-box w-xs border p-4">
          <label class="label">用户名</label>
          <input type="email" class="input" placeholder="请输入用户名" />

          <label class="label">密码</label>
          <input type="password" class="input" placeholder="请输入密码" />
            <label class="label">确认密码</label>
          <input type="password" class="input" placeholder="请再次输入密码" />
          <button class="btn btn-neutral mt-4">注册</button>
          <div class="flex justify-end">
              <RouterLink :to="{name:'login-index'}"class=" btn btn-sm btn-ghost text-gray-500">去登录</RouterLink>
          </div>
        </fieldset>
    </div>
</template>

<style scoped>

</style>