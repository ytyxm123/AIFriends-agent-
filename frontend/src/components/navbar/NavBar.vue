<script>

import {defineComponent} from "vue";
import MenuIcons from "@/components/navbar/icons/MenuIcons.vue";
import HomeIcons from "@/components/navbar/icons/HomeIcons.vue";
import FriendIcons from "@/components/navbar/icons/FriendIcons.vue";
import CreateIcons from "@/components/navbar/icons/CreateIcons.vue";
import SearchIcons from "@/components/navbar/icons/SearchIcons.vue";

export default defineComponent({
  components: {SearchIcons, CreateIcons, FriendIcons, HomeIcons, MenuIcons}
})
</script>

<template>
          <div class="drawer lg:drawer-open">
          <input id="my-drawer-4" type="checkbox" class="drawer-toggle inline" />
          <div class="drawer-content">
            <!-- Navbar -->
            <nav class="navbar w-full bg-base-100 shadow-sm">
              <div class="navbar-start">
                <label for="my-drawer-4" aria-label="open sidebar" class="btn btn-square btn-ghost drawer-button">
                <MenuIcons/>
              </label>
              <div class="px-2 font-bold text-xl">AiFriends</div>
              </div>
              <div class="navbar-center w-4/5 max-w-180">
              <div class="join w-4/5 ">
                <input class="input join-item rounded-l-full w-4/5" placeholder="搜索你感兴趣的内容" />
                <button class="btn join-item rounded-r-full w=4/5 gap-0">
                  <SearchIcons/>
                  搜索</button>
              </div>
              </div>
              <div class="navbar-end">
              <button class="btn btn-ghost text-lg">登录</button>
              </div>
            </nav>
            <!-- Page content here -->
            <slot></slot>
          </div>

          <div class="drawer-side is-drawer-close:overflow-visible">
            <label for="my-drawer-4" aria-label="close sidebar" class="drawer-overlay"></label>
            <div class="flex min-h-full flex-col items-start bg-base-200 is-drawer-close:w-16 is-drawer-open:w-64">
              <ul class="menu w-full grow">
                <li>
                  <button class="is-drawer-close:tooltip is-drawer-close:tooltip-right py-3" data-tip="首页">
                    <!-- Home icon -->
                    <HomeIcons/>
                    <span class="is-drawer-close:hidden text-base ml-2 whitespace-nowrap">首页</span>
                  </button>
                </li>
                <li>
                  <button class="is-drawer-close:tooltip is-drawer-close:tooltip-right py-3" data-tip="好友">
                    <!-- Home icon -->
                    <FriendIcons/>
                    <span class="is-drawer-close:hidden text-base ml-2 whitespace-nowrap">好友</span>
                  </button>
                </li>
                <li>
                  <button class="is-drawer-close:tooltip is-drawer-close:tooltip-right py-3" data-tip="创作">
                    <!-- Home icon -->
                    <CreateIcons/>
                    <span class="is-drawer-close:hidden text-base ml-2 whitespace-nowrap">创作</span>
                  </button>
                </li>
                <li>
                  <button class="is-drawer-close:tooltip is-drawer-close:tooltip-right py-3" data-tip="首页">
                    <!-- Home icon -->
                    <HomeIcons/>
                    <span class="is-drawer-close:hidden text-base ml-2 whitespace-nowrap">首页</span>
                  </button>
                </li>

              </ul>
            </div>
          </div>
        </div>
</template>

<style scoped>

</style>